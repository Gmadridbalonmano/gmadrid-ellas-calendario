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


# ============================================================
# CALENDARIO BASE OFICIAL FMBM - PRIMERA FASE
# ============================================================

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


# ============================================================
# DESPLEGABLES DE ISQUAD
# ============================================================

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
    """
    Normaliza texto para comparar nombres de equipos.
    """
    return re.sub(
        r"\s+",
        " ",
        str(text).upper().strip(),
    )


# ============================================================
# NAVEGACIÓN POR ISQUAD
# ============================================================

def choose_select(frame, wanted_variants):
    """
    Busca la opción correspondiente dentro de los desplegables
    de iSquad y la selecciona.
    """

    selects = frame.locator("select")

    for i in range(selects.count()):

        select = selects.nth(i)

        try:

            options = select.locator("option")

            for j in range(options.count()):

                option = options.nth(j)

                label = option.inner_text().strip()

                normalized_label = norm(label)

                matches = any(
                    norm(wanted) in normalized_label
                    or normalized_label in norm(wanted)
                    for wanted in wanted_variants
                )

                if not matches:
                    continue

                value = option.get_attribute("value")

                print(
                    f"[SELECT] {label} -> {value}"
                )

                select.select_option(
                    value=value
                )

                frame.page.wait_for_timeout(
                    2000
                )

                return True

        except Exception:
            continue

    return False


def get_isquad_frame(page):
    """
    Abre la página de FMBM y encuentra el iframe
    que contiene iSquad.
    """

    page.goto(
        URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    page.wait_for_timeout(4000)

    for frame in page.frames:

        if (
            "resultadosbalonmano.isquad.es"
            in frame.url
        ):
            print(
                "[INFO] iframe iSquad encontrado:"
            )
            print(frame.url)

            return frame

    raise RuntimeError(
        "No se encontró el iframe público "
        "de iSquad dentro de FMBM."
    )


def configure_competition(frame):
    """
    Selecciona automáticamente:

    Temporada 2026/2027
    Campeonato Autonómico de Liga Femenino
    Liga 2ª Nacional Femenina
    Primera Fase - Grupo A
    """

    for target in TARGETS:

        selected = choose_select(
            frame,
            target,
        )

        if not selected:

            frame.page.wait_for_timeout(
                2500
            )

            selected = choose_select(
                frame,
                target,
            )

        if not selected:

            raise RuntimeError(
                "No se pudo seleccionar: "
                + target[0]
            )


# ============================================================
# LECTURA DE LOS PARTIDOS
# ============================================================

def get_all_rounds(frame):
    """
    Intenta pulsar 'Todas' para mostrar todas las jornadas.
    """

    try:

        todas = frame.get_by_text(
            "Todas",
            exact=True,
        )

        if todas.count():

            print(
                "[INFO] Pulsando 'Todas' "
                "para cargar todas las jornadas."
            )

            todas.first.click()

            frame.page.wait_for_timeout(
                3000
            )

    except Exception as error:

        print(
            "[WARN] No se pudo pulsar Todas:",
            error,
        )


def extract_match_blocks(frame):
    """
    Busca elementos HTML que contengan el nombre de GMadrid.

    Subimos por sus elementos padre hasta encontrar el bloque
    que también contiene una fecha y una hora.
    """

    team_nodes = frame.get_by_text(
        re.compile(
            r"G\s*MADRID\s*ELLAS\s*2NF",
            re.I,
        )
    )

    print(
        "[INFO] Apariciones de GMadrid encontradas:",
        team_nodes.count(),
    )

    blocks = []

    seen_texts = set()

    date_time_pattern = re.compile(
        r"\d{2}/\d{2}/20(?:26|27)"
        r"[\s\S]{0,100}"
        r"\d{1,2}:\d{2}"
    )

    for i in range(team_nodes.count()):

        node = team_nodes.nth(i)

        # Probamos varios niveles de padres.
        # Esto nos permite adaptarnos a si iSquad usa
        # tablas, divs o contenedores responsive.
        for level in range(1, 8):

            xpath = (
                "xpath="
                + "/.." * level
            )

            try:

                parent = node.locator(xpath)

                if parent.count() == 0:
                    continue

                text = parent.first.inner_text(
                    timeout=3000
                )

                text = re.sub(
                    r"\s+",
                    " ",
                    text,
                ).strip()

            except Exception:
                continue

            if TEAM not in norm(text):
                continue

            if not date_time_pattern.search(
                text
            ):
                continue

            # Evitamos duplicados:
            # cuando encontramos un bloque suficientemente
            # pequeño y útil, dejamos de subir.
            if text not in seen_texts:

                seen_texts.add(text)

                blocks.append(text)

                print(
                    "[ROW]",
                    text[:600],
                )

            break

    return blocks


def identify_match(block, jornada, base_date, rival):
    """
    Comprueba si un bloque corresponde al partido
    de una jornada concreta.
    """

    normalized = norm(block)

    if TEAM not in normalized:
        return None

    if norm(rival) not in normalized:
        return None

    date_match = re.search(
        r"(\d{2}/\d{2}/20(?:26|27))",
        block,
    )

    time_match = re.search(
        r"\b(\d{1,2}:\d{2})\b",
        block,
    )

    if not date_match or not time_match:
        return None

    date_string = date_match.group(1)

    time_string = time_match.group(1)

    match_datetime = datetime.strptime(
        date_string + " " + time_string,
        "%d/%m/%Y %H:%M",
    )

    expected_date = datetime.strptime(
        base_date,
        "%Y-%m-%d",
    ).date()

    difference = abs(
        (
            match_datetime.date()
            - expected_date
        ).days
    )

    # Permitimos reprogramaciones.
    if difference > 45:
        return None

    return match_datetime


def extract_place(block):
    """
    Intenta extraer el pabellón del bloque del partido.
    """

    # Quitamos la parte anterior a la fecha/hora.
    # El pabellón normalmente aparece después.
    date_time_match = re.search(
        r"\d{2}/\d{2}/20(?:26|27)"
        r"\s*"
        r"\d{1,2}:\d{2}",
        block,
    )

    if not date_time_match:
        return ""

    after = block[
        date_time_match.end():
    ].strip()

    # Quitamos textos de estado y botones que aparecen
    # después del pabellón.
    stop_words = [
        "Pendiente",
        "Finalizado",
        "Suspendido",
        "Aplazado",
        "Previo",
        "Streaming",
        "Estad.",
        "Directo",
        "Acta",
        "Crónica",
        "Cronica",
    ]

    cut_position = len(after)

    for word in stop_words:

        match = re.search(
            re.escape(word),
            after,
            re.I,
        )

        if match:
            cut_position = min(
                cut_position,
                match.start(),
            )

    place = after[
        :cut_position
    ].strip(" -|")

    # Si por la estructura HTML ha entrado demasiado texto,
    # no queremos meter basura en LOCATION.
    if len(place) > 200:
        place = ""

    return place


def extract_status(block):
    """
    Lee el estado del partido si aparece.
    """

    statuses = [
        "Pendiente",
        "Finalizado",
        "Suspendido",
        "Aplazado",
    ]

    for status in statuses:

        if status.upper() in block.upper():
            return status

    return ""


def extract_matches(frame):
    """
    Extrae los partidos de GMadrid eLLas.
    """

    get_all_rounds(frame)

    body = frame.locator(
        "body"
    ).inner_text()

    print(
        "[INFO] GMadrid aparece en la página:",
        TEAM in norm(body),
    )

    blocks = extract_match_blocks(
        frame
    )

    live = {}

    for (
        jornada,
        base_date,
        rival,
        home,
    ) in BASE:

        for block in blocks:

            match_datetime = identify_match(
                block,
                jornada,
                base_date,
                rival,
            )

            if not match_datetime:
                continue

            place = extract_place(
                block
            )

            status = extract_status(
                block
            )

            live[jornada] = {
                "dt": match_datetime,
                "place": place,
                "status": status,
            }

            print(
                f"[FOUND] J{jornada}: "
                f"{match_datetime:%d/%m/%Y %H:%M}"
                f" | {place}"
                f" | {status}"
            )

            break

    return live


# ============================================================
# GENERACIÓN DEL CALENDARIO ICS
# ============================================================

def escape_ics(text):

    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def generate_calendar(live):

    timestamp = (
        datetime.now(TZ)
        .astimezone(
            ZoneInfo("UTC")
        )
        .strftime(
            "%Y%m%dT%H%M%SZ"
        )
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

        info = live.get(
            jornada
        )

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
            "gmadrid-ellas-2627-"
            f"j{jornada}@gmadridsports"
        )

        description = (
            f"Jornada {jornada} - "
            "Segunda Nacional Femenina "
            "2026/27. "
            "Actualizado automáticamente "
            "desde FMBM/iSquad."
        )

        if info and info.get("status"):

            description += (
                " Estado: "
                + info["status"]
                + "."
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

        # ----------------------------------------
        # HORARIO PUBLICADO
        # ----------------------------------------

        if info:

            start = info["dt"]

            # Reservamos 1 h 30 min
            end = (
                start
                + timedelta(
                    hours=1,
                    minutes=30,
                )
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
            ]

            if location:

                output.append(
                    "LOCATION:"
                    + escape_ics(
                        location
                    )
                )

            if (
                info.get("status", "")
                .lower()
                == "suspendido"
            ):

                output.append(
                    "STATUS:CANCELLED"
                )

            else:

                output.append(
                    "STATUS:CONFIRMED"
                )

            output.append(
                "TRANSP:OPAQUE"
            )

        # ----------------------------------------
        # TODAVÍA SIN HORARIO
        # ----------------------------------------

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

        output.append(
            "END:VEVENT"
        )

    output.append(
        "END:VCALENDAR"
    )

    return (
        "\r\n".join(output)
        + "\r\n"
    )


# ============================================================
# EJECUCIÓN
# ============================================================

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

            frame = get_isquad_frame(
                page
            )

            configure_competition(
                frame
            )

            live = extract_matches(
                frame
            )

            browser.close()

        # ====================================================
        # TEST DE LA JORNADA 1
        # ====================================================

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

        # Durante esta prueba queremos comprobar
        # específicamente el horario publicado actualmente.
        if (
            live[1]["dt"].strftime(
                "%H:%M"
            )
            != "20:00"
        ):

            print(
                "[ERROR] J1 encontrada, "
                "pero la hora detectada "
                "no es 20:00.",
                file=sys.stderr,
            )

            return 3

        calendar = generate_calendar(
            live
        )

        ICS_FILE.write_text(
            calendar,
            encoding="utf-8",
            newline="",
        )

        print(
            "[DONE] Calendario actualizado:"
        )

        print(
            ICS_FILE
        )

        return 0

    except Exception as error:

        print(
            "[ERROR]",
            repr(error),
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
