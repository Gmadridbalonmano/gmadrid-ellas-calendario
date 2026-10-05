#!/usr/bin/env python3

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright


# ============================================================
# CONFIGURACION
# ============================================================

TEAM = "G MADRID ELLAS 2NF"

ICS_FILE = Path(
    "GMadrid_eLLas_2026-2027_Google_Calendar.ics"
)

FMBM_URL = (
    "https://www.fmbalonmano.com/"
    "resultados-clasificaciones"
)

ISQUAD_BASE = (
    "https://resultadosbalonmano.isquad.es/"
)

TZ = ZoneInfo("Europe/Madrid")


# ============================================================
# IDS DESCUBIERTOS EN ISQUAD
# ============================================================
#
# Estos valores los obtuvo el propio workflow
# cuando consiguio navegar correctamente:
#
# Temporada 2026/2027              -> 2627
# Campeonato Autonomico Femenino   -> 3097
# Liga 2a Nacional Femenina        -> 211913
# Primera Fase - Grupo A           -> 1040390
#
# Los usamos solamente como PLAN B.
# ============================================================

SEASON_ID = "2627"
CHAMPIONSHIP_ID = "3097"
COMPETITION_ID = "211913"
PHASE_ID = "1040390"


# ============================================================
# CALENDARIO BASE OFICIAL - PRIMERA FASE
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
# OPCIONES DE LOS DESPLEGABLES
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


# ============================================================
# UTILIDADES
# ============================================================

def norm(text):

    return re.sub(
        r"\s+",
        " ",
        str(text).upper().strip(),
    )


def page_contains_team(frame):

    try:

        body = frame.locator(
            "body"
        ).inner_text(
            timeout=10000
        )

        return TEAM in norm(body)

    except Exception:

        return False


# ============================================================
# PLAN A - ENTRAR DESDE FMBM
# ============================================================

def get_isquad_frame_from_fmbm(page):

    print(
        "[PLAN A] Abriendo FMBM..."
    )

    page.goto(
        FMBM_URL,
        wait_until="domcontentloaded",
        timeout=60000,
    )

    # Esperamos hasta 30 segundos.
    # Antes solo esperabamos 4.
    for attempt in range(30):

        for frame in page.frames:

            if (
                "resultadosbalonmano.isquad.es"
                in frame.url
            ):

                print(
                    "[PLAN A OK] iframe iSquad encontrado:"
                )

                print(
                    frame.url
                )

                return frame

        if attempt % 5 == 0:

            print(
                "[PLAN A] Esperando iframe..."
            )

        page.wait_for_timeout(
            1000
        )

    print(
        "[PLAN A FALLIDO] "
        "FMBM no ha cargado el iframe "
        "de iSquad en 30 segundos."
    )

    return None


# ============================================================
# NAVEGACION POR LOS DESPLEGABLES
# ============================================================

def choose_select(
    frame,
    wanted_variants,
):

    selects = frame.locator(
        "select"
    )

    for i in range(
        selects.count()
    ):

        select = selects.nth(i)

        try:

            options = select.locator(
                "option"
            )

            for j in range(
                options.count()
            ):

                option = options.nth(j)

                label = (
                    option
                    .inner_text()
                    .strip()
                )

                normalized_label = norm(
                    label
                )

                matches = any(

                    norm(wanted)
                    in normalized_label

                    or normalized_label
                    in norm(wanted)

                    for wanted
                    in wanted_variants
                )

                if not matches:
                    continue

                value = (
                    option
                    .get_attribute(
                        "value"
                    )
                )

                print(
                    f"[SELECT] "
                    f"{label} -> {value}"
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


def configure_competition(frame):

    print(
        "[INFO] Seleccionando competicion..."
    )

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
# PLAN B - ENTRAR DIRECTAMENTE EN ISQUAD
# ============================================================

def get_isquad_direct(page):

    print(
        "[PLAN B] Intentando acceso "
        "directo a iSquad..."
    )

    # Probamos varias combinaciones porque
    # iSquad puede cambiar los nombres de los
    # parametros entre vistas.
    candidate_urls = [

        (
            ISQUAD_BASE
            + "competicion.php"
            + f"?id={PHASE_ID}"
            + f"&id_competicion={COMPETITION_ID}"
            + "&id_territorial=21"
            + "&seleccion=0"
        ),

        (
            ISQUAD_BASE
            + "competicion.php"
            + f"?id={PHASE_ID}"
            + f"&id_categoria={CHAMPIONSHIP_ID}"
            + f"&id_competicion={COMPETITION_ID}"
            + "&id_territorial=21"
            + "&seleccion=0"
        ),

        (
            ISQUAD_BASE
            + "competicion.php"
            + f"?id={PHASE_ID}"
            + f"&id_competicion={COMPETITION_ID}"
            + "&id_superficie=1"
            + "&id_territorial=21"
            + "&seleccion=0"
        ),
    ]

    for candidate in candidate_urls:

        print(
            "[PLAN B] Probando:"
        )

        print(
            candidate
        )

        try:

            page.goto(
                candidate,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.wait_for_timeout(
                4000
            )

            if page_contains_team(
                page.main_frame
            ):

                print(
                    "[PLAN B OK] "
                    "GMadrid encontrado "
                    "directamente en iSquad."
                )

                return page.main_frame

        except Exception as error:

            print(
                "[PLAN B WARN]",
                repr(error),
            )

    print(
        "[PLAN B] Los enlaces directos "
        "no contienen todavia al equipo."
    )

    return None


# ============================================================
# OBTENER LA COMPETICION
# ============================================================

def get_competition_frame(page):

    # ------------------------
    # PLAN A
    # ------------------------

    frame = get_isquad_frame_from_fmbm(
        page
    )

    if frame is not None:

        try:

            configure_competition(
                frame
            )

            page.wait_for_timeout(
                2500
            )

            if page_contains_team(
                frame
            ):

                print(
                    "[PLAN A COMPLETADO] "
                    "GMadrid encontrado."
                )

                return frame

            print(
                "[PLAN A WARN] "
                "Se encontro iSquad, "
                "pero no aparece GMadrid."
            )

        except Exception as error:

            print(
                "[PLAN A WARN]",
                repr(error),
            )

    # ------------------------
    # PLAN B
    # ------------------------

    frame = get_isquad_direct(
        page
    )

    if frame is not None:

        return frame

    raise RuntimeError(
        "No se pudo acceder a la competicion "
        "de GMadrid ni desde FMBM ni "
        "directamente desde iSquad."
    )


# ============================================================
# MOSTRAR TODAS LAS JORNADAS
# ============================================================

def get_all_rounds(frame):

    try:

        todas = frame.get_by_text(
            "Todas",
            exact=True,
        )

        if todas.count():

            print(
                "[INFO] Pulsando 'Todas'..."
            )

            todas.first.click()

            frame.page.wait_for_timeout(
                3000
            )

    except Exception as error:

        print(
            "[WARN] No se pudo pulsar Todas:",
            repr(error),
        )


# ============================================================
# EXTRAER BLOQUES DE PARTIDOS
# ============================================================

def extract_match_blocks(frame):

    team_nodes = frame.get_by_text(
        re.compile(
            r"G\s*MADRID\s*ELLAS\s*2NF",
            re.I,
        )
    )

    print(
        "[INFO] Apariciones de GMadrid:",
        team_nodes.count(),
    )

    blocks = []

    seen_texts = set()

    date_time_pattern = re.compile(
        r"\d{2}/\d{2}/20(?:26|27)"
        r"[\s\S]{0,150}"
        r"\d{1,2}:\d{2}"
    )

    for i in range(
        team_nodes.count()
    ):

        node = team_nodes.nth(i)

        for level in range(
            1,
            9,
        ):

            xpath = (
                "xpath="
                + "/.." * level
            )

            try:

                parent = node.locator(
                    xpath
                )

                if (
                    parent.count()
                    == 0
                ):

                    continue

                text = (
                    parent
                    .first
                    .inner_text(
                        timeout=3000
                    )
                )

                text = re.sub(
                    r"\s+",
                    " ",
                    text,
                ).strip()

            except Exception:

                continue

            if (
                TEAM
                not in norm(text)
            ):

                continue

            if not (
                date_time_pattern
                .search(text)
            ):

                continue

            if (
                text
                not in seen_texts
            ):

                seen_texts.add(
                    text
                )

                blocks.append(
                    text
                )

                print(
                    "[ROW]",
                    text[:600],
                )

            break

    return blocks


# ============================================================
# IDENTIFICAR PARTIDO
# ============================================================

def identify_match(
    block,
    base_date,
    rival,
):

    normalized = norm(
        block
    )

    if (
        TEAM
        not in normalized
    ):

        return None

    if (
        norm(rival)
        not in normalized
    ):

        return None

    date_match = re.search(
        r"(\d{2}/\d{2}/20(?:26|27))",
        block,
    )

    time_match = re.search(
        r"\b(\d{1,2}:\d{2})\b",
        block,
    )

    if (
        not date_match
        or not time_match
    ):

        return None

    match_datetime = datetime.strptime(
        date_match.group(1)
        + " "
        + time_match.group(1),
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


# ============================================================
# EXTRAER PABELLON
# ============================================================

def extract_place(block):

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
        "Cronica",
        "Crónica",
    ]

    cut_position = len(
        after
    )

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
    ].strip(
        " -|"
    )

    if len(place) > 200:

        return ""

    return place


# ============================================================
# EXTRAER ESTADO
# ============================================================

def extract_status(block):

    statuses = [
        "Pendiente",
        "Finalizado",
        "Suspendido",
        "Aplazado",
    ]

    for status in statuses:

        if (
            status.upper()
            in block.upper()
        ):

            return status

    return ""


# ============================================================
# EXTRAER TODOS LOS PARTIDOS
# ============================================================

def extract_matches(frame):

    get_all_rounds(
        frame
    )

    body = frame.locator(
        "body"
    ).inner_text()

    print(
        "[INFO] GMadrid aparece en pagina:",
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
# FORMATO ICS
# ============================================================

def escape_ics(text):

    return (
        str(text)
        .replace(
            "\\",
            "\\\\",
        )
        .replace(
            ";",
            "\\;",
        )
        .replace(
            ",",
            "\\,",
        )
        .replace(
            "\n",
            "\\n",
        )
    )


# ============================================================
# GENERAR CALENDARIO
# ============================================================

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
                f"🤾 GMadrid eLLas - "
                f"{rival}"
            )

            default_place = (
                "Colegio Santa Joaquina "
                "de Vedruna, "
                "Travesía de Costa Brava 3, "
                "28034 Madrid"
            )

        else:

            title = (
                f"🤾 {rival} - "
                "GMadrid eLLas"
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
            "Actualizado automaticamente "
            "desde FMBM/iSquad."
        )

        if (
            info
            and info.get(
                "status"
            )
        ):

            description += (
                " Estado: "
                + info["status"]
                + "."
            )

        output += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{timestamp}",
            (
                "SUMMARY:"
                f"{escape_ics(title)}"
            ),
            (
                "DESCRIPTION:"
                f"{escape_ics(description)}"
            ),
        ]

        # ----------------------------------------
        # HORARIO PUBLICADO
        # ----------------------------------------

        if info:

            start = info[
                "dt"
            ]

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
                info.get(
                    "status",
                    "",
                ).lower()
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
        # SIN HORARIO
        # ----------------------------------------

        else:

            date = datetime.strptime(
                base_date,
                "%Y-%m-%d",
            ).date()

            next_date = (
                date
                + timedelta(
                    days=1
                )
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
        "\r\n".join(
            output
        )
        + "\r\n"
    )


# ============================================================
# EJECUCION
# ============================================================

def main():

    try:

        with sync_playwright() as playwright:

            browser = (
                playwright
                .chromium
                .launch(
                    headless=True
                )
            )

            page = browser.new_page(
                viewport={
                    "width": 1600,
                    "height": 1000,
                }
            )

            frame = get_competition_frame(
                page
            )

            live = extract_matches(
                frame
            )

            browser.close()

        # ====================================================
        # CONTROL DE SEGURIDAD
        # ====================================================
        #
        # La J1 ya esta publicada.
        #
        # Si desaparece, asumimos que ha cambiado
        # la web y NO sobrescribimos el calendario.
        # ====================================================

        if 1 not in live:

            print(
                "[ERROR] CONTROL DE SEGURIDAD: "
                "no se ha podido leer la J1.",
                file=sys.stderr,
            )

            print(
                "[ERROR] El archivo ICS "
                "NO sera modificado.",
                file=sys.stderr,
            )

            return 2

        print(
            "[CONTROL OK] J1:"
        )

        print(
            f"[CONTROL OK] "
            f"{live[1]['dt']:%d/%m/%Y %H:%M}"
        )

        print(
            "[INFO] Partidos con horario "
            f"detectados: {len(live)}"
        )

        # ====================================================
        # GENERAR EL ICS SOLO DESPUES DEL CONTROL
        # ====================================================

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

        print(
            "[ERROR] El archivo ICS "
            "NO sera modificado.",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
