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
        "No aparece el iframe."
    )

    return None


# ============================================================
# SELECCIONAR COMPETICION
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

                value = option.get_attribute(
                    "value"
                )

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
                2000
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
# PLAN B - ACCESO DIRECTO
# ============================================================

def get_isquad_direct(page):

    print(
        "[PLAN B] Intentando acceso "
        "directo a iSquad..."
    )

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
                    "GMadrid encontrado."
                )

                return page.main_frame

        except Exception as error:

            print(
                "[PLAN B WARN]",
                repr(error),
            )

    return None


# ============================================================
# OBTENER COMPETICION
# ============================================================

def get_competition_frame(page):

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

        except Exception as error:

            print(
                "[PLAN A WARN]",
                repr(error),
            )

    frame = get_isquad_direct(
        page
    )

    if frame is not None:

        return frame

    raise RuntimeError(
        "No se pudo acceder "
        "a la competicion."
    )


# ============================================================
# QUITAR MODAL / OVERLAY
# ============================================================

def neutralize_modal(frame):

    try:

        frame.evaluate(
            """
            () => {
                const modal =
                    document.querySelector(
                        '#pdcc-modal-bg'
                    );

                if (modal) {
                    modal.style.display = 'none';
                    modal.style.pointerEvents = 'none';
                }

                document.querySelectorAll(
                    'dialog'
                ).forEach(dialog => {
                    dialog.style.display = 'none';
                    dialog.style.pointerEvents = 'none';
                });
            }
            """
        )

    except Exception:

        pass


# ============================================================
# SELECCIONAR UNA JORNADA
# ============================================================

def select_round(frame, jornada):

    neutralize_modal(
        frame
    )

    print(
        f"[JORNADA {jornada}] Seleccionando..."
    )

    # --------------------------------------------------------
    # PRIMER INTENTO:
    # buscar botones/enlaces con el numero exacto
    # --------------------------------------------------------

    candidates = frame.get_by_text(
        str(jornada),
        exact=True,
    )

    print(
        f"[JORNADA {jornada}] "
        f"Candidatos encontrados: "
        f"{candidates.count()}"
    )

    for i in range(
        candidates.count()
    ):

        candidate = candidates.nth(i)

        try:

            candidate.click(
                force=True,
                timeout=3000,
            )

            frame.page.wait_for_timeout(
                2500
            )

            body = frame.locator(
                "body"
            ).inner_text()

            # Buscamos el encabezado de la jornada.
            if re.search(
                rf"JORNADA\s*{jornada}\b",
                body,
                re.I,
            ):

                print(
                    f"[JORNADA {jornada}] "
                    "Seleccionada correctamente."
                )

                return True

        except Exception:

            continue

    # --------------------------------------------------------
    # SEGUNDO INTENTO:
    # Javascript
    # --------------------------------------------------------

    print(
        f"[JORNADA {jornada}] "
        "Intentando JavaScript..."
    )

    try:

        clicked = frame.evaluate(
            """
            (roundNumber) => {

                const elements =
                    Array.from(
                        document.querySelectorAll(
                            'a, button, li, div, span'
                        )
                    );

                const candidates =
                    elements.filter(el =>
                        el.textContent.trim()
                        === String(roundNumber)
                    );

                for (
                    const candidate
                    of candidates
                ) {

                    try {

                        candidate.click();

                        return true;

                    } catch (e) {
                    }
                }

                return false;
            }
            """,
            jornada,
        )

        if clicked:

            frame.page.wait_for_timeout(
                2500
            )

            print(
                f"[JORNADA {jornada}] "
                "Clic JavaScript realizado."
            )

            return True

    except Exception as error:

        print(
            f"[JORNADA {jornada}] "
            "Error JavaScript:",
            repr(error),
        )

    print(
        f"[JORNADA {jornada}] "
        "No se pudo seleccionar."
    )

    return False


# ============================================================
# BUSCAR BLOQUE DE GMADRID EN LA JORNADA ACTUAL
# ============================================================

def find_gmadrid_block(frame):

    team_nodes = frame.get_by_text(
        re.compile(
            r"G\s*MADRID\s*ELLAS\s*2NF",
            re.I,
        )
    )

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

                if parent.count() == 0:
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

            if TEAM not in norm(
                text
            ):

                continue

            if not date_time_pattern.search(
                text
            ):

                continue

            return text

    return None


# ============================================================
# EXTRAER DATOS DEL PARTIDO
# ============================================================

def extract_match_data(
    block,
    jornada,
    base_date,
    rival,
):

    if not block:

        return None

    normalized = norm(
        block
    )

    if norm(rival) not in normalized:

        print(
            f"[JORNADA {jornada}] "
            "El rival encontrado no coincide."
        )

        print(
            "[ROW]",
            block[:500],
        )

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

    if difference > 45:

        print(
            f"[JORNADA {jornada}] "
            "Fecha demasiado alejada "
            "del calendario base."
        )

        return None

    # --------------------------------------------------------
    # PABELLON
    # --------------------------------------------------------

    date_time_match = re.search(
        r"\d{2}/\d{2}/20(?:26|27)"
        r"\s*"
        r"\d{1,2}:\d{2}",
        block,
    )

    place = ""

    if date_time_match:

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

            place = ""

    # --------------------------------------------------------
    # ESTADO
    # --------------------------------------------------------

    status = ""

    for possible_status in [
        "Pendiente",
        "Finalizado",
        "Suspendido",
        "Aplazado",
    ]:

        if (
            possible_status.upper()
            in block.upper()
        ):

            status = (
                possible_status
            )

            break

    return {
        "dt": match_datetime,
        "place": place,
        "status": status,
    }


# ============================================================
# RECORRER LAS 14 JORNADAS
# ============================================================

def extract_all_matches(frame):

    live = {}

    print(
        "[INFO] Iniciando recorrido "
        "J1 -> J14."
    )

    for (
        jornada,
        base_date,
        rival,
        home,
    ) in BASE:

        selected = select_round(
            frame,
            jornada,
        )

        if not selected:

            print(
                f"[WARN] J{jornada}: "
                "no se pudo abrir."
            )

            continue

        block = find_gmadrid_block(
            frame
        )

        if not block:

            print(
                f"[WARN] J{jornada}: "
                "no se encontro el partido "
                "de GMadrid."
            )

            continue

        print(
            f"[ROW J{jornada}]",
            block[:500],
        )

        info = extract_match_data(
            block,
            jornada,
            base_date,
            rival,
        )

        if not info:

            print(
                f"[WARN] J{jornada}: "
                "no se pudieron extraer "
                "los datos."
            )

            continue

        live[jornada] = info

        print(
            f"[FOUND] J{jornada}: "
            f"{info['dt']:%d/%m/%Y %H:%M}"
            f" | {info['place']}"
            f" | {info['status']}"
        )

    return live


# ============================================================
# ESCAPAR ICS
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

        # ====================================================
        # HORARIO PUBLICADO
        # ====================================================

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

        # ====================================================
        # SIN HORARIO PUBLICADO
        # ====================================================

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

            live = extract_all_matches(
                frame
            )

            browser.close()

        # ====================================================
        # CONTROL DE SEGURIDAD
        # ====================================================

        if 1 not in live:

            print(
                "[ERROR] CONTROL DE SEGURIDAD: "
                "no se ha podido leer la J1.",
                file=sys.stderr,
            )

            print(
                "[ERROR] El ICS NO sera modificado.",
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

        print(
            "[INFO] Jornadas detectadas:",
            sorted(
                live.keys()
            ),
        )

        # ====================================================
        # GENERAR ICS
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
            "[ERROR] El ICS NO sera modificado.",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":

    raise SystemExit(
        main()
    )
