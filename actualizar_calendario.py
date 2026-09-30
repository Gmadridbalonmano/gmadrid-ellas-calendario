#!/usr/bin/env python3

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright


TEAM = "G MADRID ELLAS 2NF"

ICS_FILE = Path(
    "GMadrid_eLLas_2026-2027_Google_Calendar.ics"
)

URL = (
    "https://www.fmbalonmano.com/"
    "resultados-clasificaciones"
)

TZ = ZoneInfo("Europe/Madrid")


# Calendario oficial FMBM - Primera fase
BASE = [
    (1, "2026-10-04", "GRUPO EGIDO BM PINTO 2NF", True),
    (2, "2026-10-18", "CB PARLA 2NF", False),
    (3, "2026-10-25", "BALONMANO LEGANES 2NF", True),
    (
        4,
        "2026-11-08",
        "CLUB BALONMANO ALCOBENDAS 2NF",
        False,
    ),
    (5, "2026-11-15", "CAB CONCE 1NF", False),
    (
        6,
        "2026-11-22",
        "AD BALONMANO VILLAVICIOSA DE ODON 2NF",
        True,
    ),
    (7, "2026-11-29", "CORAZONISTAS 2NF", False),
    (
        8,
        "2026-12-13",
        "GRUPO EGIDO BM PINTO 2NF",
        False,
    ),
    (9, "2027-01-17", "CB PARLA 2NF", True),
    (
        10,
        "2027-01-24",
        "BALONMANO LEGANES 2NF",
        False,
    ),
    (
        11,
        "2027-01-31",
        "CLUB BALONMANO ALCOBENDAS 2NF",
        True,
    ),
    (12, "2027-02-07", "CAB CONCE 1NF", True),
    (
        13,
        "2027-02-14",
        "AD BALONMANO VILLAVICIOSA DE ODON 2NF",
        False,
    ),
    (14, "2027-02-21", "CORAZONISTAS 2NF", True),
]


# Opciones que el robot debe seleccionar en la web
TARGETS = [
    [
        "2026/2027",
        "2026-2027",
        "2026 / 2027",
    ],
    [
        "CAMPEONATO AUTONÓMICO DE LIGA FEMENINO",
        "CAMPEONATO AUTONOMICO DE LIGA FEMENINO",
    ],
    [
        "LIGA 2ª NACIONAL FEMENINA",
        "LIGA 2º NACIONAL FEMENINA",
        "2ª NACIONAL FEMENINA",
    ],
    [
        "PRIMERA FASE - GRUPO A",
        "PRIMERA FASE GRUPO A",
    ],
]


def norm(text):
    return re.sub(
        r"\s+",
        " ",
        text.upper().strip(),
    )


def choose_select(frame, wanted_variants):
    """
    Busca en los desplegables de iSquad una opción
    coincidente y la selecciona.
    """

    selects = frame.locator("select")

    for i in range(selects.count()):
        select = selects.nth(i)

        try:
            options = select.locator("option")

            for j in range(options.count()):
                label = options.nth(j).inner_text().strip()
                normalized_label = norm(label)

                matches = any(
                    norm(wanted) in normalized_label
                    or normalized_label in norm(wanted)
                    for wanted in wanted_variants
                )

                if matches:
                    value = options.nth(j).get_attribute(
                        "value"
                    )

                    print(
                        f"[SELECT] {label} -> {value}"
                    )

                    select.select_option(value=value)

                    frame.page.wait_for_timeout(1800)

                    return True

        except Exception:
            pass

    return False


def get_isquad_frame(page):
    """
    Abre FMBM y localiza el iframe de iSquad.
    """

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(3000)

    for frame in page.frames:
        if (
            "resultadosbalonmano.isquad.es"
            in frame.url
        ):
            return frame

    raise RuntimeError(
        "No se encontró el iframe público "
        "de iSquad dentro de FMBM."
    )


def configure_competition(frame):
    """
    Selecciona:
    2026/27
    Campeonato Autonómico Liga Femenino
    Liga 2ª Nacional Femenina
    Primera Fase - Grupo A
    """

    for target in TARGETS:

        if not choose_select(frame, target):

            frame.page.wait_for_timeout(2500)

            if not choose_select(frame, target):

                raise RuntimeError(
                    "No se pudo seleccionar: "
                    + target[0]
                )


def extract_matches(frame):
    """
    Lee todos los partidos de GMadrid eLLas
    que aparecen en la competición.
    """

    # Intentamos mostrar todas las jornadas
    try:
        todas = frame.get_by_text(
            "Todas",
            exact=True,
        )

        if todas.count():
            todas.first.click()
            frame.page.wait_for_timeout(2500)

    except Exception:
        pass

    body = frame.locator("body").inner_text()

    print(
        "[INFO] GMadrid aparece en la página:",
        TEAM in body.upper(),
    )

    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in body.splitlines()
        if line.strip()
    ]

    live = {}

    date_re = re.compile(
        r"(\d{2}/\d{2}/20(?:26|27))"
        r"\s*"
        r"(\d{1,2}:\d{2})"
    )

    for idx, line in enumerate(lines):

        if TEAM not in line.upper():
            continue

        window = lines[
            max(0, idx - 3):
            min(len(lines), idx + 9)
        ]

        text = " | ".join(window)

        date_match = date_re.search(text)

        if not date_match:
            continue

        match_datetime = datetime.strptime(
            date_match.group(1)
            + " "
            + date_match.group(2),
            "%d/%m/%Y %H:%M",
        )

        for (
            jornada,
            base_date,
            rival,
            home,
        ) in BASE:

            if norm(rival) not in norm(text):
                continue

            base = datetime.strptime(
                base_date,
                "%Y-%m-%d",
            ).date()

            difference = abs(
                (
                    match_datetime.date()
                    - base
                ).days
            )

            # Permitimos cambios de fecha
            if difference > 45:
                continue

            place = ""

            for candidate in window:
                candidate_upper = (
                    candidate.upper()
                )

                place_words = (
                    "PABELL",
                    "POLIDEPORT",
                    "COL.",
                    "COLEGIO",
                    "PM ",
                    "P.M.",
                    "CENTRO DEPORTIVO",
                )

                if any(
                    word in candidate_upper
                    for word in place_words
                ):
                    place = candidate
                    break

            live[jornada] = {
                "dt": match_datetime,
                "place": place,
            }

            print(
                f"[FOUND] J{jornada}: "
                f"{match_datetime:%d/%m/%Y %H:%M}"
                f" | {place}"
            )

    return live


def escape_ics(text):
    """
    Escapa caracteres especiales del formato ICS.
    """

    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generate_calendar(live):
    """
    Genera el calendario ICS manteniendo
    UID fijo para cada jornada.
    """

    timestamp = (
        datetime.now(TZ)
        .astimezone(ZoneInfo("UTC"))
        .strftime("%Y%m%dT%H%M%SZ")
    )

    output = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        (
            "PRODID:-//GMadrid Sports//"
            "eLLas 2026-2027//ES"
        ),
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        (
            "X-WR-CALNAME:"
            "GMadrid eLLas 2026-2027"
        ),
        "X-WR-TIMEZONE:Europe/Madrid",
        (
            "REFRESH-INTERVAL;"
            "VALUE=DURATION:PT6H"
        ),
        "X-PUBLISHED-TTL:PT6H",
    ]

    for (
        jornada,
        base_date,
        rival,
        home,
    ) in BASE:

        info = live.get(jornada)

        if home:
            title = (
                f"🤾 GMadrid eLLas - {rival}"
            )

            default_place = (
                "Colegio Santa Joaquina "
                "de Vedruna, "
                "Travesía de Costa Brava 3, "
                "28034 Madrid"
            )

        else:
            title = (
                f"🤾 {rival} - GMadrid eLLas"
            )

            default_place = ""

        uid = (
            f"gmadrid-ellas-2627-j"
            f"{jornada}@gmadridsports"
        )

        description = (
            f"Jornada {jornada} - "
            "Segunda Nacional Femenina "
            "2026/27. "
            "Actualizado automáticamente "
            "desde FMBM/iSquad."
        )

        output += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{timestamp}",
            f"SUMMARY:{escape_ics(title)}",
            (
                "DESCRIPTION:"
                f"{escape_ics(description)}"
            ),
        ]

        # Si la Federación ya ha publicado
        # fecha y hora
        if info:

            start = info["dt"]

            # Duración provisional del evento:
            # 1 h 30 min
            end = start + timedelta(
                hours=1,
                minutes=30,
            )

            location = (
                info["place"]
                or default_place
            )

            output += [
                (
                    "DTSTART;"
                    "TZID=Europe/Madrid:"
                    f"{start:%Y%m%dT%H%M%S}"
                ),
                (
                    "DTEND;"
                    "TZID=Europe/Madrid:"
                    f"{end:%Y%m%dT%H%M%S}"
                ),
                (
                    "LOCATION:"
                    f"{escape_ics(location)}"
                ),
                "STATUS:CONFIRMED",
                "TRANSP:OPAQUE",
            ]

        # Si todavía no hay horario,
        # mantenemos el partido como día completo
        else:

            date = datetime.strptime(
                base_date,
                "%Y-%m-%d",
            ).date()

            next_date = (
                date
                + timedelta(days=1)
            )

            output += [
                (
                    "DTSTART;VALUE=DATE:"
                    f"{date:%Y%m%d}"
                ),
                (
                    "DTEND;VALUE=DATE:"
                    f"{next_date:%Y%m%d}"
                ),
            ]

            if default_place:
                output.append(
                    "LOCATION:"
                    + escape_ics(
                        default_place
                    )
                )

            output += [
                "STATUS:TENTATIVE",
                "TRANSP:TRANSPARENT",
            ]

        output.append("END:VEVENT")

    output.append("END:VCALENDAR")

    return (
        "\r\n".join(output)
        + "\r\n"
    )


def main():

    try:

        with sync_playwright() as playwright:

            browser = (
                playwright.chromium.launch(
                    headless=True
                )
            )

            page = browser.new_page(
                viewport={
                    "width": 1600,
                    "height": 1000,
                }
            )

            frame = get_isquad_frame(page)

            configure_competition(frame)

            live = extract_matches(frame)

            browser.close()

        # TEST PRINCIPAL
        # La J1 debe existir
        if 1 not in live:

            print(
                "[ERROR] TEST J1: "
                "no se localizó "
                "GMadrid-Pinto "
                "con fecha y hora.",
                file=sys.stderr,
            )

            return 2

        print(
            "[TEST J1 OK] "
            f"{live[1]['dt']:%d/%m/%Y %H:%M}"
        )

        # Para nuestra primera prueba,
        # sabemos que FMBM muestra las 20:00
        if (
            live[1]["dt"].strftime("%H:%M")
            != "20:00"
        ):

            print(
                "[ERROR] J1 encontrada, "
                "pero la hora no es 20:00.",
                file=sys.stderr,
            )

            return 3

        calendar = generate_calendar(live)

        ICS_FILE.write_text(
            calendar,
            encoding="utf-8",
            newline="",
        )

        print(
            f"[DONE] Actualizado {ICS_FILE}"
        )

        return 0

    except Exception as error:

        print(
            "[ERROR]",
            error,
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
