#!/usr/bin/env python3

import re
import sys
import html
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


TEAM = "G MADRID ELLAS 2NF"

ICS_FILE = Path(
    "GMadrid_eLLas_2026-2027_Google_Calendar.ics"
)

TZ = ZoneInfo("Europe/Madrid")


# ============================================================
# URL DIRECTA ISQUAD
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
# CALENDARIO BASE
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

    # Actualizado segun iSquad
    (5, "2026-11-15", "CAB CONCE 2NF", False),

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

    # Actualizado segun iSquad
    (12, "2027-02-07", "CAB CONCE 2NF", True),

    (
        13,
        "2027-02-14",
        "AD BALONMANO VILLAVICIOSA DE ODON 2NF",
        False,
    ),

    (14, "2027-02-21", "CORAZONISTAS 2NF", True),
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
# LOCALIZAR PARTIDO GMADRID
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

    for index, line in enumerate(lines):

        if TEAM not in norm(line):
            continue

        start = max(
            0,
            index - 3,
        )

        end = min(
            len(lines),
            index + 12,
        )

        return " ".join(
            lines[start:end]
        )

    return None


# ============================================================
# EXTRAER PABELLON AUNQUE NO HAYA HORA
# ============================================================

def extract_place_without_time(
    block,
    rival,
):

    normalized = norm(
        block
    )

    if norm(rival) not in normalized:
        return ""

    # Buscamos el texto que aparece después de los equipos.
    # Paramos antes del estado del partido.

    stop_words = [
        "Pendiente",
        "Finalizado",
        "Suspendido",
        "Aplazado",
        "No disponible",
    ]

    cut_position = len(
        block
    )

    for word in stop_words:

        match = re.search(
            re.escape(word),
            block,
            re.I,
        )

        if match:

            cut_position = min(
                cut_position,
                match.start(),
            )

    before_status = block[
        :cut_position
    ]

    # Patrones habituales de pabellones en iSquad.
    patterns = [
        r"(COL\.\s+[^|]+?\([^)]+\))",
        r"(PM\s+[^|]+?\([^)]+\))",
        r"(PABELLON\s+[^|]+?\([^)]+\))",
        r"(PISTA\s+[^|]+?\([^)]+\))",
        r"(POLIDEPORTIVO\s+[^|]+?\([^)]+\))",
        r"(CENTRO DEPORTIVO\s+[^|]+?\([^)]+\))",
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            before_status,
            re.I,
        )

        if matches:

            place = matches[-1]

            return re.sub(
                r"\s+",
                " ",
                place,
            ).strip()

    return ""


# ============================================================
# EXTRAER DATOS
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
            "el rival no coincide."
        )

        print(
            f"[ROW J{jornada}] "
            f"{block[:500]}"
        )

        return None

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

    # --------------------------------------------------------
    # PABELLON
    # --------------------------------------------------------

    place = extract_place_without_time(
        block,
        rival,
    )

    # --------------------------------------------------------
    # FECHA Y HORA
    # --------------------------------------------------------

    date_match = re.search(
        r"(\d{2}/\d{2}/20(?:26|27))",
        block,
    )

    time_match = re.search(
        r"\b(\d{1,2}:\d{2})\b",
        block,
    )

    # Si todavía no hay hora, conservamos igualmente
    # pabellón y estado.
    if (
        not date_match
        or not time_match
    ):

        return {
            "dt": None,
            "place": place,
            "status": status,
        }

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

    if difference > 60:

        print(
            f"[WARN] J{jornada}: "
            "fecha demasiado alejada "
            "del calendario base."
        )

        return {
            "dt": None,
            "place": place,
            "status": status,
        }

    return {
        "dt": match_datetime,
        "place": place,
        "status": status,
    }


# ============================================================
# CONSULTAR JORNADAS 1-14
# ============================================================

def extract_all_matches():

    matches = {}

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
            f"[JORNADA {jornada}] Consultando..."
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

            continue

        matches[
            jornada
        ] = info

        if info["dt"]:

            print(
                f"[FOUND] J{jornada}: "
                f"{info['dt']:%d/%m/%Y %H:%M}"
                f" | {info['place']}"
                f" | {info['status']}"
            )

        else:

            print(
                f"[FOUND SIN HORA] J{jornada}: "
                f"{info['place']}"
                f" | {info['status']}"
            )

    return matches


# ============================================================
# FORMATO ICS
# ============================================================

def escape_ics(text):

    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


# ============================================================
# GENERAR CALENDARIO
# ============================================================

def generate_calendar(matches):

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

        info = matches.get(
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
        # HORA PUBLICADA
        # ====================================================

        if (
            info
            and info.get("dt")
        ):

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
                info.get("place")
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
        # TODAVIA SIN HORA
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

            # Prioridad:
            # pabellon publicado en iSquad
            # > pabellon local conocido
            location = ""

            if info:

                location = (
                    info.get("place")
                    or ""
                )

            if not location:

                location = (
                    default_place
                )

            if location:

                output.append(
                    "LOCATION:"
                    + escape_ics(
                        location
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

        matches = extract_all_matches()

        # ====================================================
        # CONTROL DE SEGURIDAD
        # ====================================================

        if (
            1 not in matches
            or not matches[1].get("dt")
        ):

            print(
                "[ERROR] CONTROL DE SEGURIDAD: "
                "no se ha podido leer "
                "correctamente la J1.",
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
            f"{matches[1]['dt']:%d/%m/%Y %H:%M}"
        )

        with_time = [
            jornada
            for jornada, info
            in matches.items()
            if info.get("dt")
        ]

        with_place = [
            jornada
            for jornada, info
            in matches.items()
            if info.get("place")
        ]

        print(
            "[INFO] Jornadas localizadas:",
            sorted(
                matches.keys()
            ),
        )

        print(
            "[INFO] Jornadas con horario:",
            sorted(
                with_time
            ),
        )

        print(
            "[INFO] Jornadas con pabellon:",
            sorted(
                with_place
            ),
        )

        # ====================================================
        # GENERAR ICS
        # ====================================================

        calendar = generate_calendar(
            matches
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
