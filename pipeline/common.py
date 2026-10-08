"""Shared helpers: name keys, casing, name matching, town and street keys, cuisine rules and money benchmarks.

Adapted from wa-eats/pipeline/common.py (itself from wi-eats and chi-eats: the same rules, learned on Chicago, Wisconsin and
Washington), with Washington-only words taken out and California ones added. Street keys keep their directions ("N Main St" and
"S Main St" are different streets in Los Angeles and San Diego), and `street_eq` forgives a source that leaves the direction out.
"""
import os, re, unicodedata
from rapidfuzz import fuzz

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(DATA, "raw")
CA = os.path.join(DATA, "ca")

STOP = {"THE", "INC", "LLC", "CO", "CORP", "RESTAURANT", "RESTAURANTS", "AND", "OF", "LTD", "CAFE", "#"}


def norm_name(s):
    # accents off first: "Taco María" must key like "Taco Maria" (a bare [^A-Z] strip made it "TACO MAR A")
    s = "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))
    s = s.upper().replace("&", " AND ").replace("'S", "S").replace("’S", "S")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b\d{2,}\b", " ", s)  # store numbers like "#1234"
    return " ".join(w for w in s.split() if w not in STOP)


SMALL = {"of", "and", "the", "on", "at", "in", "de", "la", "el", "y", "du"}
NOT_ACRONYM = {"mr", "mrs", "ms", "st", "dr", "jr", "sr", "pl", "ct", "rd", "ln", "blvd", "pkwy", "hwy", "sq", "cr", "th", "nd", "mc",
               "cty", "hwy", "trl", "cir", "ste", "fl", "wy", "pkwy", "rr", "rt", "ne", "nw", "se", "sw"}
UNIT_TAIL = re.compile(r"(\s+(BLDG|BLD|STE|SUITE|FL|FLR|FLOOR|UNIT|RM|LOWER LEVEL|LL|APT|SPACE)\b.*$)|(\s+\d+\s*$)", re.I)


def _case(w, first, addr):
    lw = w.lower()
    if not lw:
        return w
    if first is False and lw in SMALL and not addr:
        return lw
    if lw == "bj's":
        return "BJ's"
    core = re.sub(r"[^a-z']", "", lw)
    if re.fullmatch(r"(bbq|ii|iii|iv|usa|jj|kfc|ihop|tgi|atm|llc|bp|dj|pb|vfw|amvets|ymca|uw|[a-z])", core):
        return w.upper()
    if addr and re.fullmatch(r"(ne|nw|se|sw|us|ca|sr|i|n|s|e|w|pch)", core):
        return w.upper()
    if re.fullmatch(r"(dj|bj|jj)'s", core):
        return core[:2].upper() + core[2:] + w[len(core):]
    if not addr and core not in NOT_ACRONYM and re.fullmatch(r"[b-df-hj-np-tv-xz]{2,4}", core) and not re.search(r"(.)\1\1", core):
        return w.upper()
    # a stall or unit code that mixes letters and digits stays as written ("F9F10", "B12"), but not an ordinal ("1st", "22nd")
    if addr and re.search(r"\d", core + lw) and re.search(r"[a-z]", lw) and not re.fullmatch(r"\d+(st|nd|rd|th)\W*", lw):
        return w.upper()
    if re.match(r"^mc[a-z]{3}", lw):
        return "Mc" + lw[2].upper() + lw[3:]
    if re.match(r"^o'[a-z]{2}", lw):
        return "O'" + lw[2].upper() + lw[3:]
    t = lw[:1].upper() + lw[1:]
    return re.sub(r"([-(.&])([a-z])", lambda m: m.group(1) + m.group(2).upper(), t)


def nice(s, addr=False):
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = re.sub(r"(?i)\b(\w+)IES'S\b", r"\1IE'S", s)
    s = re.sub(r"(?i)'S\s+'S\b", "'S", s)
    s = re.sub(r"(?i)\bMC\s+([A-Z]{2,})", r"MC\1", s)
    if addr:   # "55 E MAIN ST STE 4" -> drop the dangling unit / stray number
        m = re.match(r"^(\d+[A-Z]?(?:\s*-\s*\d+)?\s+.+?\b(?:ST|AVE|BLVD|DR|RD|PL|CT|PKWY|TER|WAY|LN|HWY|PLZ|SQ|CIR|TRL|MARKET)\b)", s, re.I)
        if m and UNIT_TAIL.search(s[m.end():]):
            s = m.group(1)
    if not s:
        return s
    out = []
    words = s.split(" ")
    for i, w in enumerate(words):
        parts = re.split(r"([/@&])", w)
        cased = "".join(p if p in "/@&" else _case(p, None if i == 0 and j == 0 else False, addr) for j, p in enumerate(parts))
        if i and re.fullmatch(r"\(?ca\)?[\d,]*", w.lower()) and (i == len(words) - 1 or "(" in w):   # the state code
            cased = w.upper()
        out.append(cased)
    return " ".join(out).replace("Chick-Fil-A", "Chick-fil-A")


# California spellings: official names that map listings and records write several ways
TOWN_ALIAS = {"sanbuenaventura": "Ventura", "cityofsanbuenaventura": "Ventura", "industry": "City of Industry", "cityofindustry": "City of Industry",
              "lacanadaflintridge": "La Cañada Flintridge", "lacanada": "La Cañada Flintridge", "canadaflintridge": "La Cañada Flintridge",
              "carmel": "Carmel-by-the-Sea", "carmelbythesea": "Carmel-by-the-Sea", "elpasoderobles": "Paso Robles", "pasorobles": "Paso Robles",
              "marinadelrey": "Marina del Rey", "sanfran": "San Francisco", "sanfrancisco": "San Francisco", "sanfranciscoca": "San Francisco",
              "losangelesca": "Los Angeles", "losangeles": "Los Angeles", "sandiegoca": "San Diego", "sanjoseca": "San Jose", "sanjose": "San Jose",
              "sacramentoca": "Sacramento", "venturaca": "Ventura", "lajolla": "La Jolla", "delmar": "Del Mar", "elcajon": "El Cajon",
              "elcentro": "El Centro", "elmonte": "El Monte", "southelmonte": "South El Monte", "elsegundo": "El Segundo", "elsobrante": "El Sobrante",
              "lahabra": "La Habra", "lamesa": "La Mesa", "lamirada": "La Mirada", "lapuente": "La Puente", "laquinta": "La Quinta",
              "laverne": "La Verne", "lapalma": "La Palma", "lacrescenta": "La Crescenta", "losgatos": "Los Gatos", "losaltos": "Los Altos",
              "losbanos": "Los Banos", "losalamitos": "Los Alamitos", "lososos": "Los Osos", "delrey": "Del Rey", "delreyoaks": "Del Rey Oaks",
              "sthelena": "St. Helena", "saint helena": "St. Helena", "mountshasta": "Mount Shasta", "venicebeach": "Venice",
              "cardiffbythesea": "Cardiff", "cardiff": "Cardiff", "riosdelmar": "Rio del Mar", "valleyvillage": "Valley Village",
              "northhollywood": "North Hollywood", "nohollywood": "North Hollywood", "mcclellanpark": "McClellan Park", "mckinleyville": "McKinleyville",
              "mcfarland": "McFarland", "mccloud": "McCloud", "mcarthur": "McArthur", "lagunabeach": "Laguna Beach", "lagunaniguel": "Laguna Niguel",
              "lagunahills": "Laguna Hills", "lagunawoods": "Laguna Woods", "ranchosantamargarita": "Rancho Santa Margarita",
              "ranchocucamonga": "Rancho Cucamonga", "ranchopalosverdes": "Rancho Palos Verdes", "ranchomirage": "Rancho Mirage",
              "ranchocordova": "Rancho Cordova", "ranchosantafe": "Rancho Santa Fe", "palmdesert": "Palm Desert", "palmsprings": "Palm Springs",
              "cathedralcity": "Cathedral City", "desothotsprings": "Desert Hot Springs", "deserthotsprings": "Desert Hot Springs",
              "twentyninepalms": "Twentynine Palms", "29palms": "Twentynine Palms", "southlaketahoe": "South Lake Tahoe", "tahoecity": "Tahoe City",
              "mammothlakes": "Mammoth Lakes", "bigbearlake": "Big Bear Lake", "bigbear": "Big Bear Lake", "yosemitenationalpark": "Yosemite Valley",
              "yosemitevalley": "Yosemite Valley", "pacificgrove": "Pacific Grove", "halfmoonbay": "Half Moon Bay", "morrobay": "Morro Bay",
              "pismobeach": "Pismo Beach", "avilabeach": "Avila Beach", "sanluisobispo": "San Luis Obispo", "slo": "San Luis Obispo",
              "santabarbara": "Santa Barbara", "santacruz": "Santa Cruz", "santamonica": "Santa Monica", "santaana": "Santa Ana",
              "santaclarita": "Santa Clarita", "santarosa": "Santa Rosa", "santaclara": "Santa Clara", "santamaria": "Santa Maria",
              "southsanfrancisco": "South San Francisco", "southpasadena": "South Pasadena", "southgate": "South Gate",
              "westhollywood": "West Hollywood", "weho": "West Hollywood", "westcovina": "West Covina", "westsacramento": "West Sacramento",
              "eastlosangeles": "East Los Angeles", "eastpaloalto": "East Palo Alto", "paloalto": "Palo Alto", "menlopark": "Menlo Park",
              "redwoodcity": "Redwood City", "dalycity": "Daly City", "unioncity": "Union City", "fostercity": "Foster City",
              "culvercity": "Culver City", "studiocity": "Studio City", "shermanoaks": "Sherman Oaks", "vannuys": "Van Nuys",
              "panoramacity": "Panorama City", "nationalcity": "National City", "imperialbeach": "Imperial Beach", "chulavista": "Chula Vista",
              "huntingtonbeach": "Huntington Beach", "huntingtonpark": "Huntington Park", "newportbeach": "Newport Beach", "longbeach": "Long Beach",
              "redondobeach": "Redondo Beach", "hermosabeach": "Hermosa Beach", "manhattanbeach": "Manhattan Beach", "sealbeach": "Seal Beach",
              "solanabeach": "Solana Beach", "grovebeach": "Grover Beach", "groverbeach": "Grover Beach", "ventura": "Ventura"}


def canon_city(c):
    """One spelling per town: St/Saint -> St., Mt/Mount -> Mount, Ft -> Fort, "City of X" -> X (but City of Industry), case fixes."""
    if not isinstance(c, str) or not c.strip():
        return None
    # a comma or a space must come first: a bare "ca$" took the end off Santa Monica and Pacifica
    c = re.sub(r"(?:,\s*|\s+)(?:CA|Calif\.?|California)\.?(?:\s+\d{5}(?:-\d{4})?)?$", "", c.strip().strip(","), flags=re.I).strip(" ,")
    c = re.sub(r"^(?:City|Town)\s+of\s+", "", c, flags=re.I)
    if not c:
        return None
    c = nice(c) if c.isupper() or c.islower() else c
    c = re.sub(r"\b(?:Saint|St)\b\.?\s*", "St. ", c)
    c = re.sub(r"\bMt\b\.?\s*", "Mount ", c)
    c = re.sub(r"\bFt\b\.?\s*", "Fort ", c)
    c = re.sub(r"\s+", " ", c).strip()
    key = re.sub(r"[^a-z]", "", c.lower())
    return TOWN_ALIAS.get(key, c)


def town_key(c):
    k = c.lower().replace(".", " ")
    k = re.sub(r"^(e|n|s|w)\s+", lambda m: {"e": "east ", "n": "north ", "s": "south ", "w": "west "}[m.group(1)], k)
    k = re.sub(r"\bmt\b", "mount", k); k = re.sub(r"\bhts\b", "heights", k); k = re.sub(r"\bft\b", "fort", k)
    return re.sub(r"[^a-z]", "", k)


# ---------------------------------------------------------------- street keys (directions kept: N Main St and S Main St differ)
_DIR = {"NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W", "NORTHEAST": "NE", "NORTHWEST": "NW", "SOUTHEAST": "SE", "SOUTHWEST": "SW",
        "N": "N", "S": "S", "E": "E", "W": "W", "NE": "NE", "NW": "NW", "SE": "SE", "SW": "SW"}
_TYPE = {"STREET": "ST", "ST": "ST", "AVENUE": "AVE", "AVE": "AVE", "AV": "AVE", "BOULEVARD": "BLVD", "BLVD": "BLVD", "ROAD": "RD", "RD": "RD",
         "DRIVE": "DR", "DR": "DR", "PLACE": "PL", "PL": "PL", "COURT": "CT", "CT": "CT", "LANE": "LN", "LN": "LN", "HIGHWAY": "HWY", "HWY": "HWY",
         "PARKWAY": "PKWY", "PKWY": "PKWY", "WAY": "WAY", "WY": "WAY", "TERRACE": "TER", "TER": "TER", "CIRCLE": "CIR", "CIR": "CIR", "LOOP": "LOOP",
         "PLAZA": "PLZ", "PLZ": "PLZ", "SQUARE": "SQ", "SQ": "SQ", "TRAIL": "TRL", "TRL": "TRL", "MALL": "MALL", "CRESCENT": "CRES", "ALLEY": "ALY",
         "EXPRESSWAY": "EXPY", "EXPY": "EXPY", "FREEWAY": "FWY", "FWY": "FWY", "ROW": "ROW", "WALK": "WALK", "PIKE": "PIKE", "BYPASS": "BYP",
         "CROSSING": "XING", "XING": "XING", "RUN": "RUN", "PASS": "PASS", "PT": "PT", "POINT": "PT", "LOOP RD": "LOOP"}
_ORD = {"FIRST": "1ST", "SECOND": "2ND", "THIRD": "3RD", "FOURTH": "4TH", "FIFTH": "5TH", "SIXTH": "6TH", "SEVENTH": "7TH", "EIGHTH": "8TH",
        "NINTH": "9TH", "TENTH": "10TH", "ELEVENTH": "11TH", "TWELFTH": "12TH"}


def road(a):
    """One spelling for numbered roads: 'State Route 1' = 'SR-1' = 'CA-1' = 'Hwy 1' = 'Highway 1'; 'US Highway 101' = 'US-101' = 'Hwy 101'
    (a bare highway number that is a US route in California stays a US route); 'Interstate 5' = 'I 5'; 'PCH' = 'Pacific Coast Hwy'."""
    a = a.upper()
    a = re.sub(r"\bPCH\b", "PACIFIC COAST HWY", a)
    a = re.sub(r"\b(?:STATE\s+(?:ROUTE|HIGHWAY|HWY|RTE|RD|ROAD)|STATE\s+RT|SR|CA|CALIFORNIA\s+(?:HIGHWAY|HWY|STATE\s+ROUTE))\s*-?\s*(\d+)\b", r"SR \1", a)
    a = re.sub(r"\b(?:US|U\s+S)\s*(?:HIGHWAY|HWY|ROUTE|RTE)?\s*-?\s*(\d+)\b", r"US \1", a)
    a = re.sub(r"\b(?:INTERSTATE|I)\s*-?\s*(\d+)\b", r"I \1", a)
    a = re.sub(r"\b(?:HIGHWAY|HWY)\s+(\d+)\b", lambda m: ("US " if m.group(1) in US_ROUTES else "SR ") + m.group(1), a)
    return a


US_ROUTES = {"101", "395", "50", "199", "97", "6", "95", "40"}   # the US highways that run through California


def street_key(a):
    """'2746 NE 45th St' -> ('2746', 'NE 45TH'); '2746 Northeast 45TH Street' -> the same; '100 4th Ave N' -> ('100', '4TH N');
    '14200 1ST AVE S, F' -> ('14200', '1ST S'); '20829 Hwy 99' -> ('20829', 'SR 99')."""
    if not isinstance(a, str):
        return None, None
    a = road(a.split(",")[0])
    a = re.sub(r"[.#]", " ", a).replace("-", " ") if not re.match(r"^\s*\d+\s*-\s*\d+\s", a) else re.sub(r"[.#]", " ", a)
    m = re.match(r"^\s*(\d+)[A-Z]?(?:\s*-\s*\d+[A-Z]?)?\s+(.*)$", a)
    if not m:
        return None, None
    words = [w for w in m.group(2).replace("-", " ").split() if w]
    out, pre, post, seen_type = [], None, None, False
    if words and words[0] in _DIR and len(words) > 1:
        pre = _DIR[words[0]]; words = words[1:]
    for j, w in enumerate(words):
        if w in ("STE", "SUITE", "UNIT", "APT", "SPC", "SPACE", "BLDG", "FL", "RM", "#", "LOWER", "UPPER") or re.fullmatch(r"[A-Z]?\d+[A-Z]?", w) and seen_type:
            break
        if w in _DIR and out:
            post = _DIR[w]; break
        if w in _TYPE and out and not (w == "WAY" and j == 0):
            seen_type = True
            continue
        if seen_type:
            break
        out.append(_ORD.get(w, w))
    core = " ".join(out[:3])
    if not core:
        return None, None
    return m.group(1), " ".join(x for x in (pre, core, post) if x)


_DIRS = r"(?:N|S|E|W|NE|NW|SE|SW)"


def undir(k):
    """'NE NORTHUP' -> 'NORTHUP'; '4TH N' -> '4TH'. For matching when one source leaves the direction out."""
    return re.sub(rf"^{_DIRS} | {_DIRS}$", "", k) if isinstance(k, str) else k


def street_eq(a, b):
    """Same street: equal keys, or equal once directions are dropped when one side has none ('NORTHUP' = 'NE NORTHUP',
    but '4TH N' != '4TH S')."""
    if not a or not b:
        return False
    return a == b or (undir(a) == undir(b) and (a == undir(a) or b == undir(b)))


def street_nums(a):
    """'157-159 Main St' -> {'157', '159'}; '2505 Pacific Ave' -> {'2505'}."""
    if not isinstance(a, str):
        return set()
    m = re.match(r"^\s*(\d+)[A-Z]?(?:\s*-\s*(\d+)[A-Z]?)?\s", a.upper() + " ")
    if not m:
        return set()
    lo = int(m.group(1)); hi = int(m.group(2)) if m.group(2) else lo
    if hi < lo:   # "1500-02"
        hi = int(str(lo)[: len(str(lo)) - len(m.group(2))] + m.group(2)) if m.group(2) else lo
    return {str(x) for x in range(lo, hi + 1, 2 if (hi - lo) % 2 == 0 else 1)} if 0 <= hi - lo <= 12 else {str(lo)}


# words that don't identify a business on their own: a name match needs a shared word outside this list
GENERIC = set("""PIZZA PIZZERIA PHO TACO TACOS TAQUERIA GRILL GRILLE KITCHEN EXPRESS HOUSE COFFEE BAR PUB TAVERN FOOD FOODS STORE SHOP MARKET
DELI BAKERY CHICKEN FISH BBQ SUSHI THAI CHINESE MEXICAN INDIAN ITALIAN GYROS BURGER BURGERS WINGS DONUTS DONUT BEEF TEA JUICE
NORTH SOUTH EAST WEST PARK SQUARE STATION UNION TOWN VILLAGE STREET AVE AVENUE CENTER PLAZA LAKE LAKES RIVER BAY
NEW OLD BEST GOLDEN LITTLE BIG KING STAR ORIGINAL FAMOUS FRESH HOT GRAND LA EL LOS LAS DE DEL ON THE Y AT OF LOUNGE SNACK SNACKS
NOODLE NOODLES ASIAN SHRIMP PATIO CLUB SUPPER INN LODGE SALOON RESORT BREWING BREWERY COMPANY BREW HALL CUSTARD FROZEN CHEESE CURDS
FRY BRATS BRAT WISCONSIN BAKE CAFETERIA CORNER SPOT STOP PLACE ROOM SPORTS FAMILY STEAKHOUSE STEAK DINER CREAMERY ICE CREAM
MKE MILW HUT WOK MEAL FUSION BUFFET CUISINE EATS EATERY
CALIFORNIA CALI CA LA SF SD OC SOCAL NORCAL BAY PACIFIC COAST COASTAL BEACH VALLEY OCEAN SUNSET GOLDEN STATE WEST COAST TERIYAKI ESPRESSO
BURRITO BURRITOS MARISCOS BIRRIA TORTAS HARBOR ISLAND DRIVE THRU IN DOGS POKE BOWL BOWLS ROLL ROLLS HAWAIIAN FILIPINO JAPANESE KOREAN
BOBA DIM SUM DUMPLING DUMPLINGS POT SMOOTHIE SMOOTHIES ACAI CREPE CREPES WINE WINERY CELLARS VINEYARD VINEYARDS TASTING VEGAN TOFU""".split())


def _stems(s):
    return {w if w in GENERIC else (w[:-1] if len(w) > 3 and w.endswith("S") else w) for w in s.split()} - GENERIC


def name_sim(a, b):
    ours, theirs = set(a.split()), set(b.split())
    distinct = (_stems(a) - GENERIC) & (_stems(b) - GENERIC)
    joined = a.replace(" ", "") == b.replace(" ", "") or fuzz.ratio(a.replace(" ", ""), b.replace(" ", "")) >= 92
    if joined:
        return 96
    if not distinct and fuzz.ratio(a, b) < 95:   # nothing but generic words in common: not the same business
        return 60
    s_set = fuzz.token_set_ratio(a, b)
    # token_set_ratio is 100 whenever one name's words are a subset of the other's: cap it unless the overlap is a real share of both
    if len(ours & theirs) < 0.5 * min(len(ours), len(theirs)) + 0.5 or len(ours & theirs) < 0.4 * max(len(ours), len(theirs)):
        s_set = min(s_set, 72)
    return max(s_set, fuzz.ratio(a, b), fuzz.token_sort_ratio(a, b))


FOODCAT = re.compile(r"\b(restaurant|cafe|coffee|bakery|pizza|bar|pub|diner|deli|taco|ice cream|donut|dessert|sandwich|food court|caterer|tea house|bistro|brewpub|brewery|juice|grill|takeout|buffet|bagel|chicken|seafood|steak|hot dog|tavern|lounge|gastropub|snack|yogurt|creperie|patisserie|chocolate|confectionery|bubble tea|night club|beer|wine|bbq|barbecue|pie|pastry|popcorn|tamale|churro|takeaway|tortilleria|supper club|custard|fish & chips|cheesesteak)\b", re.I)
NOTFOOD = re.compile(r"^(?:Tower|Museum|Stadium|Convention|Hotel|Performing|Theater|Hospital|University|Corporate|Observation|Tourist|Airport|Casino|Gas station|Grocery|Supermarket|Convenience|Liquor store|Event|Banquet|Park|Arena)\b")

# Name keywords -> cuisine. Whole words only, so HOSPITAL isn't "PITA", BREWING isn't "WING", BOWLING isn't "BOWL".
# Order matters: specific before general.
_W = lambda words: re.compile(r"\b(?:" + words + r")\b")
CUISINE_RULES = [
    ("Hot Dogs", _W(r"HOT ?DOGS?|DOG HAUS|PINKS|WIENERSCHNITZEL|WIENERS?|BRATS?|BRATWURST|SAUSAGES?|FRANKS?|CORN DOGS?")),
    ("Pizza", _W(r"PIZZA|PIZZAS|PIZZERIA|PIZZERIAS|DOMINOS|PAPA JOHNS|LITTLE CAESARS?|ROUND TABLE|MOUNTAIN MIKES|STRAW HAT|WOODSTOCKS|PIEOLOGY|ZPIZZA|ME N EDS|NAPOLETANA|MOD PIZZA|BLAZE|SLICE HOUSE")),
    ("Hawaiian", _W(r"HAWAIIAN|HAWAII|ALOHA|LOCO MOCO|MUSUBI|KONA|L AND L|ONO|MAHALO|LUAU|KAU KAU|PLATE LUNCH|SHAVE ICE")),
    ("Filipino", _W(r"FILIPINO|PINOY|LUMPIA|ADOBO|SISIG|MANILA|JOLLIBEE|SILOG|TAPSILOG|LECHON|CHIBOG|KAMAYAN|INASAL|GOLDILOCKS|CHOWKING|CHOW KING|TURO TURO|ULAM|HALO HALO|UBE")),
    ("Korean", _W(r"KOREAN?|KOREA|KIMCHI|BIBIMBAP|SEOUL|GOGI|BULGOGI|KBBQ|CUPBOP|SOONDUBU|TOFU HOUSE|BCD|BONCHON|KYOCHON|GALBI|KALBI|JJIGAE|PAIK|HODORI")),
    ("Thai", _W(r"THAI|SIAM|BANGKOK|ISAAN|ISAN|LAO|LAOTIAN|LAOS")),
    ("Vietnamese", _W(r"PHO|VIETNAMESE|VIETNAM|SAIGON|BANH MI|BANH|HANOI|BUN BO|COM TAM")),
    ("Coffee & Café", _W(r"COFFEE|ESPRESSO|STARBUCKS|DUNKIN|CAFFE|TEA|TEAS|TEAHOUSE|BOBA|LATTE|ROASTERS?|ROASTING|KAFFE|KAFFEE|PEETS|PHILZ|BLUE BOTTLE|VERVE|SIGHTGLASS|COFFEE BEAN|DUTCH BROS|BARISTAS?|JAVA|MOCHA|CAFFEINE|AMERICANO|SHARETEA|GONG CHA|KUNG FU TEA|7 LEAVES|TPUMPS|TAPIOCA|MILK ?TEA|MATCHA|BOBA GUYS")),
    ("Bakery & Sweets", _W(r"BAKERY|BAKERIES|BAKESHOP|BAKE SHOP|BAKEHOUSE|PASTRY|PASTRIES|PATISSERIE|DONUTS?|DOUGHNUTS?|PANADERIA|CAKES?|CUPCAKES?|COOKIES?|DESSERTS?|ICE CREAM|GELATO|GELATERIA|PALETERIA|PALETAS|YOGURT|YOGURTLAND|PINKBERRY|FROYO|CREPES?|CREPERIE|SWEETS|CHOCOLATE|CHOCOLATIER|CINNABON|BAGELS?|CREAMERY|CHURROS?|PIES|CONFECTIONS?|MICHOACANA|DAIRY QUEEN|BASKIN|PORTOS|85C|MOCHI|WINCHELLS|YUM YUM|SHAVED ICE|RASPADOS?|MALASADAS?")),
    ("Mexican", _W(r"TAQUERIA|TAQUERIAS|TACOS?|MEXICAN[AO]?|MEXICO|BURRITOS?|BIRRIA|BIRRIERIA|CARNITAS|TAMALES?|TORTAS?|ELOTES?|MARISCOS|CHIPOTLE|QDOBA|AZTECA|JALISCO|MICHOACAN|GUADALAJARA|OAXACA|OAXAQUENA|GUERRERO|PUEBLA|SINALOA|NAYARIT|ZACATECAS|SONORA|SONORAN|CANTINA|TORTILLERIA|ANTOJITOS?|QUESADILLAS?|NACHOS?|HUARACHES?|FONDA|EL TORO|DEL TACO|EL POLLO LOCO|RUBIOS|BAJA FRESH|BAJA|WAHOOS|ROBERTOS|ALBERTOS|FILIBERTOS|ALBERTACOS|LOLITAS|POZOLE|MENUDO|CHILE VERDE|TLAYUDAS?|SOPES|GORDITAS?|CHILAQUILES|AGUAS FRESCAS|MOLE")),
    ("Latin & Caribbean", _W(r"CUBAN[AO]?|CUBA|PUERTO RICAN|BORINQUEN|CARIBBEAN|JAMAICAN?|JERK|HAITIAN?|PERUVIAN|PERU|COLOMBIAN[AO]?|COLOMBIA|SALVADOREN[AO]|PUPUSAS?|PUPUSERIA|ARGENTIN[AE]|ARGENTINIAN|VENEZUELAN?|AREPAS?|BRAZILIAN?|EMPANADAS?|DOMINICAN|GUATEMALTEC[AO]|HONDUREN[AO]|ECUADORIAN|NICARAGUAN?|LATIN[AO]?|CEVICHE|POLLO CAMPERO|CHURRASCARIA|BELIZEAN")),
    ("Japanese & Sushi", _W(r"SUSHI|RAMEN|JAPANESE|JAPAN|IZAKAYA|HIBACHI|OMAKASE|TOKYO|BENTO|UDON|SOBA|YAKITORI|KATSU|TONKATSU|SAKE|TEMPURA|SASHIMI|TEPPANYAKI|KYOTO|OSAKA|BENIHANA|ONIGIRI|DONBURI|OKONOMIYAKI|TAKOYAKI|TERIYAKI|YOSHINOYA|KURA|SUSHIRO|SHABU|GYUDON|CURRY HOUSE|COCO ICHIBANYA")),
    ("Chinese", _W(r"CHINA|CHINESE|EGG ROLLS?|WOK|DUMPLINGS?|DIM SUM|PANDA EXPRESS|HUNAN|SZECHUAN|SZECHWAN|SICHUAN|MANDARIN|CANTONESE|KUNG PAO|HONG KONG|BEIJING|SHANGHAI|HOT ?POT|CHOP SUEY|BAO|LO MEIN|WONTON|PEKING|YUNNAN|TAIWANESE|TAIWAN|DIN TAI FUNG|XIAO LONG BAO|XLB|CHINATOWN|NOODLE HOUSE|HAKKA|HAINAN|CONGEE|DUCK HOUSE|BBQ PORK|MALA|XIAN|BIANG")),
    ("South Asian", _W(r"INDIA|INDIAN|TANDOOR|TANDOORI|CURRY|CURRIES|MASALA|BIRYANI|NEPAL|NEPALI|NEPALESE|HIMALAYAN?|PAKISTANI?|BOMBAY|MUMBAI|DELHI|PUNJAB|PUNJABI|KATHMANDU|MOMOS?|CHAAT|SAMOSAS?|BENGALI|BANGLADESHI|SRI LANKAN?|DOSA|TIKKA|AFGHAN|KABUL")),
    ("Mediterranean & Middle Eastern", _W(r"GREEK|GYROS?|MEDITERRANEAN|MEDITERANNEAN|FALAFEL|SHAWARMA|MIDDLE EASTERN|LEBANESE|HALAL|KABOBS?|KEBABS?|KABABS?|PERSIAN|IRANIAN|TURKISH|ISRAELI|HUMMUS|PITA|PITAS|ZAATAR|SYRIAN|ARABIC|ARABIAN|ATHENS|OLYMPIA|PARTHENON|AEGEAN|MEZZE|ASSYRIAN|YEMENI|ARMENIAN|ZANKOU|LAVASH|GLENDALE KABOB|IRAQI|JORDANIAN|PALESTINIAN|EGYPTIAN|KOSHARI")),
    ("African", _W(r"AFRICAN?|AFRICA|ETHIOPIAN?|NIGERIAN?|ERITREAN?|GHANAIAN|SENEGALESE|SOMALI|MOROCCAN|KENYAN|CAMEROONIAN|JOLLOF|SUYA|INJERA")),
    ("Italian", _W(r"ITALIAN[AO]?|ITALIA|TRATTORIA|OSTERIA|PASTA|RISTORANTE|VINO|NONNA|CUCINA|ENOTECA|SPAGHETTI|NAPOLI|SICILIAN|TUSCANY|TUSCAN|FORNO|MAGGIANOS|OLIVE GARDEN|BUCA DI BEPPO|PASTARIA|GNOCCHI|RAVIOLI")),
    ("Burgers", _W(r"BURGERS?|HAMBURGERS?|CHEESEBURGERS?|MCDONALDS|MC DONALDS|WENDYS|WHITE CASTLE|FIVE GUYS|SHAKE SHACK|SMASHBURGER|PATTY|PATTIES|STEAK N SHAKE|SONIC|ARBYS|CHECKERS|JACK IN THE BOX|CARLS JR|IN N OUT|HABIT|RED ROBIN|FATBURGER|TOMMYS|FARMER BOYS|JOHNNY ROCKETS|NATIONS|FOSTERS FREEZE|BURGERIM|ORIGINAL TOMMYS|DRIVE IN|HAMBURGER|BURGER KING|ASTRO BURGER|BOB S BIG BOY|BOBS BIG BOY")),
    ("Seafood", _W(r"SEAFOOD|FISH|FISHERIES|FISHERY|FISHERMANS|SHRIMP|OYSTERS?|CRABS?|CRAB|LOBSTER|CATFISH|CAJUN|BOIL|BOILING|POKE|CHOWDER|CLAMS?|SALMON|HALIBUT|ABALONE|SCALLOPS?|LONG JOHN SILVERS|FISH AND CHIPS|BOILING CRAB|HOOK AND REEL|SHELLFISH|RAW BAR")),
    ("Chicken & Wings", _W(r"CHICKEN|WINGS|POPEYES|KFC|CHURCHS|RAISING CANES?|CHICK FIL A|BROASTED|WINGSTOP|NASHVILLE HOT|KRISPY KRUNCHY|DAVES HOT|HOT CHICKEN|ROTISSERIE|POLLO")),
    ("BBQ", _W(r"BBQ|BAR B Q|BAR BQ|BAR B QUE|BAR BE CUE|BAR B CUE|BARBECUE|BARBEQUE|RIBS|SMOKEHOUSE|SMOKED|BRISKET|FAMOUS DAVES|TRI TIP|SANTA MARIA STYLE")),
    ("Sandwiches & Deli", _W(r"SANDWICH|SANDWICHES|DELI|DELICATESSEN|SUBWAY|JIMMY JOHNS|POTBELLY|JERSEY MIKES|FIREHOUSE SUBS|SUBS|HOAGIES?|PANERA|CORNER BAKERY|CHEESE ?STEAKS?|PHILLY|CAPRIOTTIS|SUB SHOP|TOGOS|IKES|LEES SANDWICHES|MENDOCINO FARMS|DIBELLAS|QUIZNOS|CHARLEYS|BRISTOL")),
    ("Steakhouse", _W(r"STEAK|STEAKS|STEAKHOUSE|STEAK HOUSE|CHOPHOUSE|CHOP HOUSE|RUTHS CHRIS|CAPITAL GRILLE|MORTONS|TEXAS ROADHOUSE|LONGHORN|OUTBACK|PRIME RIB|HOUSE OF PRIME RIB|LAWRYS|BLACK ANGUS|SIZZLER")),
    ("Soul & Southern", _W(r"SOUL|SOUTHERN|CREOLE|GUMBO|BISCUITS?|GRITS|CHICKEN WAFFLES|ROSCOES|NEW ORLEANS|LOUISIANA")),
    ("Healthy & Vegan", _W(r"VEGAN|VEGETARIAN|SALADS?|JUICE|JUICERY|SMOOTHIES?|SWEETGREEN|PLANT BASED|ACAI|HEALTHY|ORGANIC|JAMBA|LEMONADE|TENDER GREENS|PRESSED|JUICE IT UP|NEKTER|BOWL ?CO|URBANE CAFE|CAVA")),
    ("Breakfast & Diner", _W(r"BREAKFAST|PANCAKES?|DINER|BRUNCH|EGGS?|IHOP|DENNYS|PERKINS|YOLK|OMELETTES?|OMELETS?|SUNRISE|MORNING|WAFFLES?|GRIDDLE|SKILLETS?|BLACK BEAR DINER|COCOS|NORMS|EGGSLUT|SNOOZE|HASH HOUSE|FIRST WATCH|MARIE CALLENDERS|HOFS HUT|RUBYS DINER|DUPARS")),
    ("European", _W(r"POLISH|POLSKA|UKRAINIAN|GERMAN|BAVARIAN|SERBIAN|BOSNIAN|CROATIAN|RUSSIAN|FRENCH|BISTRO|BRASSERIE|IRISH|BRITISH|SWEDISH|NORWEGIAN|DANISH|SPANISH|TAPAS|PORTUGUESE|BASQUE|EUROPEAN|LITHUANIAN|CZECH|HUNGARIAN|ROMANIAN|GEORGIAN|PIEROGI|PIEROGIES|HAUS|BIERGARTEN|BEER GARDEN|SCHNITZEL|SWISS|FONDUE|MELTING POT|BELGIAN|DUTCH|PELMENI|PAELLA")),
    ("Bar & Pub", _W(r"PUB|TAVERN|BAR|SALOON|LOUNGE|TAP|TAPS|TAPROOM|TAPHOUSE|BREWING|BREWERY|BREWPUB|BEER|ALE HOUSE|GASTROPUB|COCKTAILS?|WINE|WINERY|WINES|CELLARS|VINEYARDS?|TASTING ROOM|DISTILLERY|DISTILLING|PADDY|BARS|SPEAKEASY|TIKI")),
]
GCAT = [(c, re.compile(p)) for c, p in [
    ("Pizza", r"Pizza"), ("Hawaiian", r"Hawaiian"), ("Filipino", r"Filipino"), ("Coffee & Café", r"Coffee|Cafe|Espresso|Tea house|Bubble tea"),
    ("Bakery & Sweets", r"Bakery|Donut|Dessert|Ice cream|Pastry|Cake|Frozen yogurt|Chocolate|Bagel|Pie shop|Candy"),
    ("Mexican", r"Mexican|Taco|Burrito|Tex-Mex|Taqueria"), ("Latin & Caribbean", r"Latin|Caribbean|Cuban|Puerto Rican|Jamaican|Peruvian|Colombian|Salvadoran|Brazilian|Venezuelan|Argentin|Haitian|Guatemalan"),
    ("Japanese & Sushi", r"Japanese|Sushi|Ramen|Teriyaki"), ("Chinese", r"Chinese|Cantonese|Dim sum|Szechuan|Dumpling|Hot pot|Taiwanese"),
    ("Korean", r"Korean"), ("Thai", r"Thai|Laotian"), ("Vietnamese", r"Vietnamese|Pho"), ("South Asian", r"Indian|Pakistani|Nepal|Bangladeshi|Sri Lankan|Afghan"),
    ("Mediterranean & Middle Eastern", r"Mediterranean|Middle Eastern|Greek|Lebanese|Falafel|Halal|Turkish|Persian|Israeli|Shawarma|Armenian"),
    ("African", r"African|Ethiopian|Nigerian|Moroccan|Eritrean|Somali"), ("Italian", r"Italian"),
    ("Hot Dogs", r"Hot dog"), ("Burgers", r"Hamburger|Burger"), ("Seafood", r"Seafood|Fish|Oyster|Poke|Cajun"),
    ("Chicken & Wings", r"Chicken"), ("BBQ", r"Barbecue"), ("Steakhouse", r"Steak"),
    ("Soul & Southern", r"Soul food|Southern"), ("Sandwiches & Deli", r"Sandwich|Deli|Cheesesteak"),
    ("Healthy & Vegan", r"Vegan|Vegetarian|Health food|Salad|Juice"), ("Breakfast & Diner", r"Breakfast|Brunch|Diner|Pancake"),
    ("European", r"French|German|Polish|Ukrainian|Spanish|Tapas|Irish|European|Eastern European|Serbian|Russian|Bistro|Scandinavian|Swiss|Belgian|Dutch|Fondue|Basque"),
    ("Bar & Pub", r"Bar\b|Pub|Brewpub|Brewery|Tavern|Gastropub|Wine bar|Cocktail|Beer|Winery"),
    # a primary "American" category is an answer too, so a later "Bar" tag doesn't turn a family restaurant into a pub
    ("American & Other", r"American restaurant|Eclectic restaurant|Fine dining restaurant|Family restaurant|Southwestern|Californian"),
]]


def cuisine(name_key, gcats, raw=""):
    for c, pat in CUISINE_RULES:
        if pat.search(name_key or ""):
            return c
    cats = [x for x in (gcats or "").split("|") if x]
    for cat in cats:
        for c, pat in GCAT:
            if pat.search(cat):
                return c
    if re.search(r"\bCAF[EÉ]\b", (raw or "").upper()) and not cats:
        return "Coffee & Café"
    return "American & Other"


# Typical food-cost % by cuisine (industry rule-of-thumb ranges, midpoint)
FOOD_COST = {"Pizza": 26, "Coffee & Café": 24, "Bakery & Sweets": 25, "Mexican": 28, "Latin & Caribbean": 30,
             "Japanese & Sushi": 34, "Chinese": 30, "Korean": 32, "Thai": 30, "Vietnamese": 30, "South Asian": 28,
             "Mediterranean & Middle Eastern": 30, "African": 30, "Italian": 29, "Hot Dogs": 31, "Hawaiian": 31, "Filipino": 30, "Burgers": 31,
             "Chicken & Wings": 33, "Seafood": 36, "BBQ": 34, "Steakhouse": 38, "Soul & Southern": 32,
             "Sandwiches & Deli": 30, "Healthy & Vegan": 32, "Breakfast & Diner": 27, "European": 30, "Bar & Pub": 27,
             "American & Other": 30}
# Pre-tax net margin benchmarks by segment
MARGIN = {1: 0.075, 2: 0.05, 3: 0.055, 4: 0.045}
MARGIN_CUISINE = {"Bar & Pub": 0.10, "Steakhouse": 0.09, "Pizza": 0.07, "Coffee & Café": 0.08}
SPEND = {1: 13, 2: 28, 3: 62, 4: 165}   # typical per-person spend by price tier
