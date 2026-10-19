"""Statyczny reference do budowania zapytan HUDOC - offline, bez sieci.

Zrodlo: HUDOC `GET /app/query/refiners?query=(contentsitename=ECHR)&refiners=...`
oraz `GET /app/odata/resources?endpoint=Taxonomy` (etykiety). Stan zweryfikowany
2026-10-19. Nic tu nie jest zgadywane: kazdy kod wystapil w odpowiedzi HUDOC.
"""

from __future__ import annotations

from . import BASE_URL

QUERY_GRAMMAR = '''\
Zapytanie HUDOC to lista warunkow sklejanych operatorem AND, np.

    (contentsitename=ECHR) AND (appno="474/21") AND (article="6-1")

Reguly:
  - `field=value` porownuje pole z wartoscia (najczesciej w cudzyslowie);
    `field:vrednost` to to samo dla pol tekstowych (np. `docname:"Shevchuk"`).
  - `kpdate` (data kluczowa) obsluguje porownania: `(kpdate>="2024-01-01")`.
  - Wyszukiwanie pelnotekstowe to fraza w cudzyslowie w nawiasie, bez prefiksu
    pola: `("right to respect for private life")`. Pole `fulltext` (shortcode
    `f`) dziala tylko w postaci grupowej - `f:"fraza"` zwraca ZERO trafien.
  - `AND`, `OR`, `NOT` lacza warunki; nawiasy sa obowiazkowe wokol kazdego warunku.
  - Zapytanie trzeba URL-enkodowac w parametrze `query`.
'''

SEARCH_FIELDS: dict[str, str] = {
    'contentsitename': 'Strona zrodlowa zbioru. Zawsze "ECHR" - konektor dokleja to sam.',
    'appno': 'Numer skargi, np. "474/21" albo "5826/03". Porownanie: (appno="474/21").',
    'article': 'Kod artykulu Konwencji/protokolu, np. "6", "6-1", "P1-1", "35-3-a".',
    'kpdate': 'Data kluczowa dokumentu (ISO, czesc data), np. (kpdate>="2024-01-01").',
    'doctype': 'Kod typu dokumentu, np. "HEJUD" (wyrok ang.), "HEDEC" (decyzja ang.).',
    'documentcollectionid2': 'Kolekcja, np. "GRANDCHAMBER" albo "CHAMBER".',
    'itemid': 'Identyfikator dokumentu w HUDOC, np. "001-250747". Shortcode: "i".',
    'isplaceholder': 'Czy to duplikat nie w jezyku podstawowym: "True" / "False".',
    'languageisocode': 'Jezyk dokumentu (ISO 639-2/B), np. "ENG", "FRE", "POL".',
    'docname': 'Tytul sprawy, np. (docname:"Shevchuk").',
    'conclusion': 'Wynik sprawy jako tekst (np. naruszenie art. 6).',
    'originatingbody': 'Organ wydajacy (kod liczbowy) - patrz ORIGINATING_BODIES.',
    'ecli': 'Identyfikator ECLI, np. "ECLI:CE:ECHR:2023:0411JUD000047421".',
}

OPERATORS: tuple[str, ...] = ("=", ":", "<=", ">=", "*", "AND", "OR", "NOT")

DOCUMENT_TYPES: dict[str, str] = {
    'ADVART47ENG': 'ADVART47ENG',
    'ADVART47FRE': 'ADVART47FRE',
    'ADVPRO16OPARM': 'ADVPRO16OPARM',
    'ADVPRO16OPCZE': 'ADVPRO16OPCZE',
    'ADVPRO16OPENG': 'ADVPRO16OPENG',
    'ADVPRO16OPFRE': 'ADVPRO16OPFRE',
    'ADVPRO16OPGER': 'ADVPRO16OPGER',
    'ADVPRO16OPHRV': 'ADVPRO16OPHRV',
    'ADVPRO16OPPOL': 'ADVPRO16OPPOL',
    'ADVPRO16OPPOR': 'ADVPRO16OPPOR',
    'ADVPRO16OPSPA': 'ADVPRO16OPSPA',
    'ADVPRO16OPUKR': 'ADVPRO16OPUKR',
    'ADVPRO16OTHENG': 'ADVPRO16OTHENG',
    'ADVPRO16OTHFRE': 'ADVPRO16OTHFRE',
    'ADVPRO16OTHGER': 'ADVPRO16OTHGER',
    'ADVPRO16REFENG': 'ADVPRO16REFENG',
    'ADVPRO16REFFRE': 'ADVPRO16REFFRE',
    'ADVPRO16REFRUM': 'ADVPRO16REFRUM',
    'ADVPRO16REFUKR': 'ADVPRO16REFUKR',
    'CLIN': 'Case-Law Information Note - Eng',
    'CLINF': 'Case-Law Information Note - Fre',
    'HDECALB': 'HDECALB',
    'HDECARA': 'HDECARA',
    'HDECARM': 'HDECARM',
    'HDECAZE': 'HDECAZE',
    'HDECBOS': 'HDECBOS',
    'HDECBUL': 'HDECBUL',
    'HDECCZE': 'HDECCZE',
    'HDECDUT': 'HDECDUT',
    'HDECEST': 'HDECEST',
    'HDECGEO': 'HDECGEO',
    'HDECGER': 'HDECGER',
    'HDECGRE': 'HDECGRE',
    'HDECHRV': 'HDECHRV',
    'HDECHUN': 'HDECHUN',
    'HDECICE': 'HDECICE',
    'HDECITA': 'HDECITA',
    'HDECLIT': 'HDECLIT',
    'HDECMAC': 'HDECMAC',
    'HDECMNE': 'HDECMNE',
    'HDECPOL': 'HDECPOL',
    'HDECPOR': 'HDECPOR',
    'HDECRUM': 'HDECRUM',
    'HDECRUS': 'HDECRUS',
    'HDECSLO': 'HDECSLO',
    'HDECSLV': 'HDECSLV',
    'HDECSPA': 'HDECSPA',
    'HDECSRP': 'HDECSRP',
    'HDECSWE': 'HDECSWE',
    'HDECTUR': 'HDECTUR',
    'HDECUKR': 'HDECUKR',
    'HECOM': 'HECOM',
    'HECOMOLD': 'HECOMOLD',
    'HEDEC': 'Decision - Eng',
    'HEGCQP': 'HEGCQP',
    'HEJP9': 'Protocol 9 Judgment - Eng',
    'HEJUD': 'Judgment - Eng',
    'HEREP': "Commission's Report - Eng",
    'HERES32': 'Resolution Article 32 - Eng',
    'HERES54': 'Resolution Article 54 - Eng',
    'HFCOM': 'HFCOM',
    'HFCOMOLD': 'HFCOMOLD',
    'HFDEC': 'Decision - Fre',
    'HFJP9': 'Protocol 9 Judgment - Fre',
    'HFJUD': 'Judgment - Fre',
    'HFREP': "Commission's Report - Fre",
    'HFRES32': 'Resolution Article 32 - Fre',
    'HFRES54': 'Resolution Article 54 - Fre',
    'HJUDALB': 'HJUDALB',
    'HJUDARA': 'HJUDARA',
    'HJUDARM': 'HJUDARM',
    'HJUDAZE': 'HJUDAZE',
    'HJUDBEL': 'HJUDBEL',
    'HJUDBOS': 'HJUDBOS',
    'HJUDBUL': 'HJUDBUL',
    'HJUDCZE': 'HJUDCZE',
    'HJUDDUT': 'HJUDDUT',
    'HJUDEST': 'HJUDEST',
    'HJUDGEO': 'HJUDGEO',
    'HJUDGER': 'HJUDGER',
    'HJUDGRE': 'HJUDGRE',
    'HJUDHRV': 'HJUDHRV',
    'HJUDHUN': 'HJUDHUN',
    'HJUDICE': 'HJUDICE',
    'HJUDITA': 'HJUDITA',
    'HJUDKOR': 'HJUDKOR',
    'HJUDLAV': 'HJUDLAV',
    'HJUDLIT': 'HJUDLIT',
    'HJUDMAC': 'HJUDMAC',
    'HJUDMNE': 'HJUDMNE',
    'HJUDPER': 'HJUDPER',
    'HJUDPOL': 'HJUDPOL',
    'HJUDPOR': 'HJUDPOR',
    'HJUDRUM': 'HJUDRUM',
    'HJUDRUS': 'HJUDRUS',
    'HJUDSLO': 'HJUDSLO',
    'HJUDSLV': 'HJUDSLV',
    'HJUDSPA': 'HJUDSPA',
    'HJUDSRP': 'HJUDSRP',
    'HJUDSWE': 'HJUDSWE',
    'HJUDTUR': 'HJUDTUR',
    'HJUDUKR': 'HJUDUKR',
    'PR': 'Press Release',
}

LANGUAGES: dict[str, str] = {
    'ALB': 'Albanian',
    'ARA': 'Arabic',
    'ARM': 'Armenian',
    'AZE': 'Azerbaijani',
    'BEL': 'Belarusian',
    'BOS': 'Bosnian',
    'BUL': 'Bulgarian',
    'CZE': 'Czech',
    'DUT': 'Dutch',
    'ENG': 'English',
    'EST': 'Estonian',
    'FRE': 'French',
    'GEO': 'Georgian',
    'GER': 'German',
    'GRE': 'Greek',
    'HRV': 'Croatian',
    'HUN': 'Hungarian',
    'ICE': 'Icelandic',
    'ITA': 'Italian',
    'KOR': 'Korean',
    'LAV': 'Latvian',
    'LIT': 'Lithuanian',
    'MAC': 'Macedonian',
    'MNE': 'Montenegrin',
    'PER': 'Persian',
    'POL': 'Polish',
    'POR': 'Portuguese',
    'RUM': 'Romanian',
    'RUS': 'Russian',
    'SLO': 'Slovak',
    'SLV': 'Slovenian',
    'SPA': 'Spanish',
    'SRP': 'Serbian',
    'SWE': 'Swedish',
    'TUR': 'Turkish',
    'UKR': 'Ukrainian',
}

ARTICLES: tuple[str, ...] = (
    '1', '2', '2-1', '2-2', '3', '4',
    '4-1', '4-2', '4-3', '4-3-a', '4-3-b', '4-3-c',
    '4-3-d', '5', '5-1', '5-1-a', '5-1-b', '5-1-c',
    '5-1-d', '5-1-e', '5-1-f', '5-2', '5-3', '5-3-c',
    '5-4', '5-5', '6', '6-1', '6-2', '6-3',
    '6-3-a', '6-3-b', '6-3-c', '6-3-d', '6-3-e', '7',
    '7-1', '7-2', '8', '8-1', '8-2', '9',
    '9-1', '9-2', '10', '10-1', '10-2', '11',
    '11-1', '11-2', '12', '12-1', '13', '14',
    '15', '15-1', '15-3', '16', '17', '18',
    '19', '20', '24', '25', '25-1', '26',
    '27', '27-1', '27-1-b', '27-2', '27-3', '28',
    '28-1', '28-1-a', '28-1-b', '28-3', '28-b', '29',
    '29-1', '29-2', '29-3', '30', '30-1', '30-1-a',
    '30-1-b', '30-1-c', '30-3', '31', '31-1', '31-3',
    '32', '32-1', '32-2', '32-3', '33', '34',
    '35', '35-1', '35-2', '35-2-b', '35-3', '35-3-a',
    '35-3-b', '35-4', '36', '36-1', '36-2', '37',
    '37-1', '37-1-a', '37-1-b', '37-1-c', '37-2', '38',
    '38-1', '38-1-a', '38-1-b', '39', '39-2', '41',
    '43', '44', '46', '46-1', '46-2', '46-4',
    '47', '48', '48-2', '52', '53', '54',
    '55', '56', '56-1', '56-3', '57', '58',
    '64', 'P1-1', 'P1-1-1', 'P1-1-2', 'P1-2', 'P1-2-2',
    'P1-3', 'P1-4', 'P1-6', 'P1-7', 'P2-1', 'P4-1',
    'P4-2', 'P4-2-1', 'P4-2-2', 'P4-2-3', 'P4-3', 'P4-3-1',
    'P4-3-2', 'P4-4', 'P4-5', 'P4-6', 'P4-6-2', 'P4-7',
    'P5-7', 'P6-1', 'P6-2', 'P6-3', 'P7-1', 'P7-1-1',
    'P7-1-2', 'P7-2', 'P7-2-1', 'P7-2-2', 'P7-3', 'P7-4',
    'P7-4-1', 'P7-4-2', 'P7-5', 'P7-6', 'P7-7', 'P7-7-2',
    'P7-8', 'P9-5', 'P11-6', 'P12-1', 'P12-2', 'P13-1',
    'P14-1',
)

COLLECTIONS: tuple[str, ...] = (
    'ADMISSIBILITY', 'ADMISSIBILITYCOM', 'ADMISSIBILITYDECISIONS', 'ADVISORYOPINIONS',
    'ARTICLE47', 'CASELAW', 'CHAMBER', 'CHAMBERJUDGMENTS',
    'CLIN', 'COMMITTEE', 'COMMUNICATEDCASES', 'COMQ',
    'DECCOMMISSION', 'DECGRANDCHAMBER', 'DECISIONS', 'DEU',
    'ELL', 'EXECUTION', 'FORTHCOMINGHEARINGS', 'FORTHCOMINGJUDGMENTS',
    'FRA', 'GCJUDGMENTS', 'GCREFERRALS', 'GCRELINQUISHMENT',
    'GENERAL', 'GRANDCHAMBER', 'HEARINGS', 'HYE',
    'ISL', 'JCT', 'JUDGMENTS', 'KAT',
    'MERITS', 'MKD', 'OPINIONS', 'OTHERREQUESTS',
    'PANELREFUSALS', 'PRESS', 'PROTOCOL16', 'QUESTIONS',
    'R39', 'REFERRALS', 'REPORTS', 'RESOLUTIONS',
    'RON', 'SCREENINGPANEL', 'SLK', 'SQI',
    'STATEMENTOFFACTS',
)

ORIGINATING_BODIES: dict[str, str] = {
    '1': 'Commission (First Chamber)',
    '2': 'Commission (Second Chamber)',
    '3': 'Commission (Plenary)',
    '4': 'Court (First Section)',
    '5': 'Court (Second Section)',
    '6': 'Court (Third Section)',
    '7': 'Court (Fourth Section)',
    '8': 'Court (Grand Chamber)',
    '9': 'Court (Chamber)',
    '15': 'Court (Plenary)',
    '16': 'Court (Screening Panel)',
    '17': 'Committee of Ministers',
    '21': 'Commission',
    '23': 'Court (Fifth Section)',
    '25': 'Court (First Section Committee)',
    '26': 'Court (Second Section Committee)',
    '27': 'Court (Third Section Committee)',
    '28': 'Court (Fourth Section Committee)',
    '29': 'Court (Fifth Section Committee)',
}


NOTES: tuple[str, ...] = (
    (
        "HUDOC zwraca HTTP 404 dla /app/query/results, gdy braku parametru `sort` - "
        "nawet pustego. Konektor zawsze wysyla `sort=`. Bez tego API nie odpowiada JSON-em."
    ),
    (
        "Pelny tekst pobiera sie jako .docx z /app/conversion/docx/?library=ECHR&id=<itemid>; "
        "wariant HTML (bez `docx`) zwraca 404."
    ),
    (
        "`isplaceholder=True` to duplikat dokumentu w jezyku niepodstawowym. Takie dokumenty "
        "nie maja konwertowalnego .docx (HTTP 500) - tekst jest pod itemid jezyka podstawowego."
    ),
    (
        "Kazdy jezyk dokumentu ma w HUDOC wlasne `itemid`, wiec `itemid` jest kluczem "
        "jezykowo-scislym; `appno` jest wspolny dla wszystkich wersji jezykowych."
    ),
    (
        "`article` to GLEBOKI kod (np. `6-1`, `35-3-a`, `P1-1`), nie sam numer artykulu: "
        '`article="6"` NIE zwroci dokumentow oznaczonych wylacznie jako `6-1`.'
    ),
    (
        "`kpdate` to data kluczowa HUDOC (zwykle data orzeczenia), a nie data uprawomocnienia "
        "ani data zdarzen. Konektor nie ma pola na date uprawomocnienia."
    ),
)


def build_filter_reference() -> dict:
    """Assemble the static HUDOC query reference (no network)."""
    return {
        "endpoint": {
            "search": f"{BASE_URL}/app/query/results",
            "full_text_docx": f"{BASE_URL}/app/conversion/docx/",
            "required_params": ["query", "select", "sort", "start", "length"],
        },
        "query_grammar": QUERY_GRAMMAR,
        "searchable_fields": SEARCH_FIELDS,
        "operators": list(OPERATORS),
        "document_types": DOCUMENT_TYPES,
        "languages": LANGUAGES,
        "articles": list(ARTICLES),
        "collections": list(COLLECTIONS),
        "originating_bodies": ORIGINATING_BODIES,
        "notes": list(NOTES),
    }
