#!/usr/bin/env python3

import re
import sys
import html
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURACION
# ============================================================

TEAM = "G MADRID ELLAS 2NF"

ICS_FILE = Path(
    "GMadrid_eLLas_2026-2027_Google_Calendar.ics"
)

TZ = ZoneInfo("Europe/Madrid")


# ============================================================
# URL DIRECTA DE ISQUAD
# ============================================================
#
# Estos parametros los hemos obtenido directamente
# observando la peticion real que hace iSquad al
# seleccionar la Jornada 2.
#
# Lo unico que cambiaremos sera jornada=1 ... jornada=14
# ============================================================

ISQUAD_URL = (
    "https://resultadosbalonmano.isquad.es/"
    "competicion.php"
    "?seleccion=0"
    "&id=1040390"
    "&id_ambito=0"
    "&id_territorial=21"
    "&id_superficie=1"
    "&iframe=0"
    "&id_categoria=3097"
    "&id_competicion=211913"
    "&jornada={jornada}"
)


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

    (
        5,
        "2026-11-15",
        "CAB CONCE 1NF",
        False,
    ),

    (
        6,
        "2026-11-22",
        "AD BALONMANO VILLAVICIOSA DE ODON 2NF",
        True,
    ),

    (
        7,
        "2026-11-29",
        "CORAZONISTAS 2NF",
        False,
    ),

    (
        8,
        "2026-12-13",
        "GRUPO EGIDO BM PINTO 2NF",
        False,
    ),

    (
        9,
        "2027-01-17",
        "CB PARLA 2NF",
        True,
    ),

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

    (
        12,
        "2027-02-07",
        "CAB CONCE 1NF",
        True,
    ),

    (
        13,
        "2027-02-14",
        "AD BALONMANO VILLAVICIOSA DE ODON 2NF",
        False,
    ),

    (
        14,
        "2027-02-21",
        "CORAZONISTAS 2NF",
        True,
    ),
]


# ============================================================
# UTILIDADES
# ============================================================

def norm(text):

    text = html.unescape(
        str(text)
    )

    return re.sub(
        r"\s+",
        " ",
        text.upper().strip(),
    )


def fetch(url):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; "
                "GMadrid-eLLas-Calendar/1.0)"
            )
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=30,
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="replace",
        )


def html_to_text(raw_html):

    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        raw_html,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"</(?:td|th|tr|div|p|li)>",
        "\n",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = html.unescape(
        text
    )

    text = text.replace(
        "\xa0",
        " ",
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n+",
        "\n",
        text,
    )

    return text.strip()


# ============================================================
# EXTRAER EL BLOQUE DE GMADRID
# ============================================================

def find_gmadrid_block(text):

    lines = [
        re.sub(
            r"\s+",
            " ",
            line,
        ).strip()

        for line in text.splitlines()

        if line.strip()
    ]

    for index, line in enumerate(
        lines
    ):

        if TEAM not in norm(
            line
        ):
            continue

        start = max(
            0,
            index - 3,
        )

        end = min(
            len(lines),
            index + 12,
        )

        block = " ".join(
            lines[start:end]
        )

        return block

    return None


# ============================================================
# EXTRAER DATOS DE UNA JORNADA
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

    if TEAM not in normalized:

        return None

    if norm(rival) not in normalized:

        print(
            f"[WARN] J{jornada}: "
            "GMadrid aparece, pero "
            "el rival no coincide."
        )

        print(
            f"[ROW J{jornada}] "
            f"{block[:500]}"
        )

        return None

    # --------------------------------------------------------
    # FECHA
    # --------------------------------------------------------

    date_match = re.search(
        r"(\d{2}/\d{2}/20(?:26|27))",
        block,
    )

    # --------------------------------------------------------
    # HORA
    # --------------------------------------------------------

    time_match = re.search(
        r"\b(\d{1,2}:\d{2})\b",
        block,
    )

    if (
        not date_match
        or not time_match
    ):

        print(
            f"[INFO] J{jornada}: "
            "partido localizado, "
            "pero aun sin fecha/hora completa."
        )

        return None

    match_datetime = datetime.strptime(
        date_match.group(1)
        + " "
        + time_match.group(1),
        "%d/%m/%Y %H:%M",
    )

    # --------------------------------------------------------
    # CONTROL DE FECHA
    # --------------------------------------------------------

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

    # Permitimos reprogramaciones amplias.
    if difference > 60:

        print(
            f"[WARN] J{jornada}: "
            "fecha detectada demasiado "
            "alejada del calendario base."
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
            "No disponible",
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
            in normalized
        ):

            status = possible_status

            break

    return {
        "dt": match_datetime,
        "place": place,
        "status": status,
    }


# ============================================================
# CONSULTAR LAS 14 JORNADAS DIRECTAMENTE
# ============================================================

def extract_all_matches():

    live = {}

    print(
        "[INFO] Consultando directamente "
        "las jornadas 1-14 en iSquad."
    )

    for (
        jornada,
        base_date,
        rival,
        home,
    ) in BASE:

        url = ISQUAD_URL.format(
            jornada=jornada
        )

        print(
            f"[JORNADA {jornada}] "
            "Consultando..."
        )

        print(
            f"[URL J{jornada}] {url}"
        )

        try:

            raw_html = fetch(
                url
            )

        except Exception as error:

            print(
                f"[WARN] J{jornada}: "
                "error descargando iSquad:",
                repr(error),
            )

            continue

        text = html_to_text(
            raw_html
        )

        block = find_gmadrid_block(
            text
        )

        if not block:

            print(
                f"[WARN] J{jornada}: "
                "no aparece GMadrid."
            )

            continue

        print(
            f"[ROW J{jornada}] "
            f"{block[:500]}"
        )

        info = extract_match_data(
            block,
            jornada,
            base_date,
            rival,
        )

        if not info:

            print(
                f"[INFO] J{jornada}: "
                "sin horario utilizable."
            )

            continue

        live[
            jornada
        ] = info

        print(
            f"[FOUND] J{jornada}: "
            f"{info['dt']:%d/%m/%Y %H:%M}"
            f" | {info['place']}"
            f" | {info['status']}"
        )

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

        # MUY IMPORTANTE:
        # UID FIJO PARA QUE GOOGLE ACTUALICE
        # EL MISMO EVENTO.
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
        # TODAVIA SIN HORARIO
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

        live = extract_all_matches()

        # ====================================================
        # CONTROL DE SEGURIDAD
        # ====================================================
        #
        # Sabemos que J1 existe y tiene horario.
        # Si deja de aparecer, NO tocamos el calendario.
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
