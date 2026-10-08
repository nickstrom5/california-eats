"""Known chain brands in California: regex on normalized name -> brand label.

Adapted from wi-eats/pipeline/brands.py (itself from chi-eats); Wisconsin-only brands dropped, California and West Coast chains added.
"""
import re

BRANDS = [
    # national
    ("Dunkin'", r"^DUNKIN"), ("Subway", r"^SUBWAY"), ("McDonald's", r"^MC ?DONALDS"), ("Starbucks", r"^STARBUCK"),
    ("Jimmy John's", r"^JIMMY JOHN"), ("Burger King", r"^BURGER KING"), ("Taco Bell", r"^TACO BELL"),
    ("Potbelly", r"^POTBELLY"), ("Wingstop", r"^WING ?STOP"), ("Chipotle", r"^CHIPOTLE"), ("Popeyes", r"^POPEYE"),
    ("Wendy's", r"^WENDYS"), ("Panda Express", r"^PANDA EXPRESS"), ("White Castle", r"^WHITE CASTLE"),
    ("Chick-fil-A", r"^CHICK FIL"), ("Domino's", r"^DOMINO"), ("Jersey Mike's", r"^JERSEY MIKE"),
    ("Panera Bread", r"^PANERA"), ("Little Caesars", r"^LITTLE CAESAR"),
    ("Papa John's", r"^PAPA JOHN"), ("KFC", r"^KFC|^KENTUCKY FRIED"), ("Tropical Smoothie Cafe", r"^TROPICAL SMOOTHIE"),
    ("Buffalo Wild Wings", r"^BUFFALO WILD"), ("Five Guys", r"^FIVE GUYS"), ("Raising Cane's", r"^RAISING CANE"),
    ("Auntie Anne's", r"^AUNTIE ANNE"), ("Qdoba", r"^QDOBA"), ("Noodles & Company", r"^NOODLES (?:AND )?CO(?:MPANY)?\b"),
    ("Smoothie King", r"^SMOOTHIE KING"), ("Firehouse Subs", r"^FIREHOUSE SUB"), ("IHOP", r"^IHOP"), ("Denny's", r"^DENNYS"),
    ("Sonic", r"^SONIC DRIVE|^SONIC$"), ("Insomnia Cookies", r"^INSOMNIA COOKIE"), ("Crumbl", r"^CRUMBL"),
    ("Dairy Queen", r"^DAIRY QUEEN|^DQ GRILL|^DQ$"), ("Baskin-Robbins", r"^BASKIN"), ("Krispy Kreme", r"^KRISPY KREME"),
    ("Chuck E. Cheese", r"^CHUCK E CHEESE"), ("Nothing Bundt Cakes", r"^NOTHING BUNDT"), ("Hooters", r"^HOOTERS"),
    ("Cheesecake Factory", r"^CHEESECAKE FACTORY"), ("P.F. Chang's", r"^P ?F CHANG"), ("Maggiano's", r"^MAGGIANO"),
    ("Ruth's Chris", r"^RUTHS CHRIS"), ("Morton's", r"^MORTONS THE STEAK|^MORTONS STEAK"), ("Steak 'n Shake", r"^STEAK N SHAKE"),
    ("Applebee's", r"^APPLEBEE"), ("Chili's", r"^CHILIS"), ("Olive Garden", r"^OLIVE GARDEN"), ("Red Lobster", r"^RED LOBSTER"),
    ("Jamba", r"^JAMBA"), ("Cinnabon", r"^CINNABON"), ("Pizza Hut", r"^PIZZA HUT"), ("Arby's", r"^ARBYS"),
    ("MOD Pizza", r"^MOD PIZZA"), ("Peet's Coffee", r"^PEETS"), ("Cava", r"^CAVA$|^CAVA (?:MEDITERRANEAN|GRILL)"),
    ("Blaze Pizza", r"^BLAZE PIZZA"), ("Texas Roadhouse", r"^TEXAS ROADHOUSE"), ("Red Robin", r"^RED ROBIN"),
    ("Papa Murphy's", r"^PAPA MURPH"), ("Marco's Pizza", r"^MARCOS PIZZA"), ("Cracker Barrel", r"^CRACKER BARREL"),
    ("Outback Steakhouse", r"^OUTBACK STEAK"), ("LongHorn Steakhouse", r"^LONGHORN STEAK"), ("Cold Stone Creamery", r"^COLD STONE"),
    ("Golden Corral", r"^GOLDEN CORRAL"), ("Einstein Bros. Bagels", r"^EINSTEIN BRO"), ("Quiznos", r"^QUIZNO"),
    ("Dickey's Barbecue Pit", r"^DICKEYS"), ("Dave's Hot Chicken", r"^DAVES HOT CHICKEN"), ("Sbarro", r"^SBARRO"),
    ("Orange Julius", r"^ORANGE JULIUS"), ("7 Brew", r"^7 BREW"), ("First Watch", r"^FIRST WATCH"), ("TGI Fridays", r"^TGI FRIDAY"),
    ("Charleys Cheesesteaks", r"^CHARLEYS"), ("Smashburger", r"^SMASHBURGER"), ("Shake Shack", r"^SHAKE SHACK"),
    ("Sweetgreen", r"^SWEETGREEN"), ("Dutch Bros", r"^DUTCH BRO"), ("Wetzel's Pretzels", r"^WETZEL"), ("Pret A Manger", r"^PRET A MANGER"),
    ("Fogo de Chão", r"^FOGO DE CHAO"), ("BJ's Restaurant & Brewhouse", r"^BJS RESTAURANT|^BJS BREWHOUSE|^BJS$"),
    ("Buca di Beppo", r"^BUCA DI BEPPO"), ("Benihana", r"^BENIHANA"), ("Kura Revolving Sushi Bar", r"^KURA (?:REVOLVING )?SUSHI|^KURA$"),
    ("Joe's Crab Shack", r"^JOES CRAB SHACK"), ("Pollo Campero", r"^POLLO CAMPERO"), ("Bonchon", r"^BONCHON"), ("Kyochon", r"^KYOCHON"),
    ("Hook & Reel", r"^HOOK AND REEL"), ("Mendocino Farms", r"^MENDOCINO FARMS"), ("Urbane Cafe", r"^URBANE CAFE"),
    ("Habit Burger Grill", r"^(?:THE )?HABIT(?: BURGER)?"), ("Wienerschnitzel", r"^WIENERSCHNITZEL"),
    ("Pieology", r"^PIEOLOGY"), ("Round Table Pizza", r"^ROUND TABLE"), ("Mountain Mike's Pizza", r"^MOUNTAIN MIKE"),
    ("Straw Hat Pizza", r"^STRAW HAT"), ("Woodstock's Pizza", r"^WOODSTOCKS"), ("Pizza Factory", r"^PIZZA FACTORY"),
    ("Me-n-Ed's Pizzeria", r"^ME N EDS"), ("Garlic Jim's", r"^GARLIC JIM"), ("Pizza My Heart", r"^PIZZA MY HEART"),
    ("zpizza", r"^ZPIZZA"), ("California Pizza Kitchen", r"^CALIFORNIA PIZZA KITCHEN|^CPK$"), ("Shakey's Pizza", r"^SHAKEYS"),
    ("Toppers Pizza", r"^TOPPERS"), ("Hungry Howie's", r"^HUNGRY HOWIE"), ("Jet's Pizza", r"^JETS PIZZA"),
    # California and West Coast
    ("In-N-Out Burger", r"^IN N OUT"), ("Eureka!", r"^EUREKA(?: BURGER| RESTAURANT GROUP| RESTAURANT)?$"), ("Jack in the Box", r"^JACK IN THE BOX"), ("Carl's Jr.", r"^CARLS JR|^CARLS JUNIOR"),
    ("Del Taco", r"^DEL TACO"), ("El Pollo Loco", r"^EL POLLO LOCO"), ("Rubio's", r"^RUBIOS"), ("Baja Fresh", r"^BAJA FRESH"),
    ("Chronic Tacos", r"^CHRONIC TACO"), ("Wahoo's Fish Taco", r"^WAHOOS"), ("Taco Bell Cantina", r"^TACO BELL CANTINA"),
    ("Yoshinoya", r"^YOSHINOYA"), ("Coffee Bean & Tea Leaf", r"^(?:THE )?COFFEE BEAN"), ("Philz Coffee", r"^PHILZ"),
    ("Blue Bottle Coffee", r"^BLUE BOTTLE"), ("Verve Coffee", r"^VERVE COFFEE"), ("Farmer Boys", r"^FARMER BOYS"),
    ("Fatburger", r"^FATBURGER"), ("Original Tommy's", r"^(?:ORIGINAL )?TOMMYS(?: ORIGINAL)?(?: WORLD FAMOUS)?(?: HAMBURGERS?)?$"),
    ("Johnny Rockets", r"^JOHNNY ROCKETS"), ("Nation's Giant Hamburgers", r"^NATIONS (?:GIANT|FOOD|HAMBURGER)"),
    ("Foster's Freeze", r"^FOSTERS FREEZE"), ("Dog Haus", r"^DOG HAUS"), ("Islands", r"^ISLANDS(?: RESTAURANT| FINE BURGERS)?$"),
    ("Lazy Dog Restaurant & Bar", r"^LAZY DOG"), ("Yard House", r"^YARD HOUSE"), ("Ruby's Diner", r"^RUBYS DINER"),
    ("Black Bear Diner", r"^BLACK BEAR DINER"), ("Coco's Bakery Restaurant", r"^COCOS (?:BAKERY|RESTAURANT)"), ("Norms", r"^NORMS(?: RESTAURANT)?$"),
    ("Marie Callender's", r"^MARIE CALLENDER"), ("Claim Jumper", r"^CLAIM JUMPER"), ("Sizzler", r"^SIZZLER"), ("Hof's Hut", r"^HOFS HUT"),
    ("Bob's Big Boy", r"^BOBS BIG BOY"), ("Mimi's Cafe", r"^MIMIS CAFE"), ("Elephant Bar", r"^ELEPHANT BAR"),
    ("Togo's", r"^TOGOS"), ("Ike's Love & Sandwiches", r"^IKES (?:LOVE|PLACE|SANDWICH)|^IKES$"), ("Lee's Sandwiches", r"^LEES SANDWICH"),
    ("Capriotti's", r"^CAPRIOTTI"), ("Lemonade", r"^LEMONADE(?: RESTAURANT)?$"), ("Tender Greens", r"^TENDER GREENS"),
    ("Native Foods", r"^NATIVE FOODS"), ("Veggie Grill", r"^VEGGIE GRILL"), ("Sharky's Woodfired Mexican Grill", r"^SHARKYS"),
    ("Pick Up Stix", r"^PICK UP STIX"), ("Pei Wei", r"^PEI WEI"), ("Din Tai Fung", r"^DIN TAI FUNG"), ("Panda Inn", r"^PANDA INN"),
    ("Pho Hoa", r"^PHO HOA"), ("Boiling Crab", r"^(?:THE )?BOILING CRAB"), ("Kickin' Crab", r"^(?:THE )?KICKIN CRAB"),
    ("Zankou Chicken", r"^ZANKOU"), ("Pollo Loco", r"^POLLO LOCO"), ("Juan Pollo", r"^JUAN POLLO"), ("Daphne's", r"^DAPHNES"),
    ("Pinkberry", r"^PINKBERRY"), ("Yogurtland", r"^YOGURTLAND"), ("Menchie's", r"^MENCHIES"), ("Golden Spoon", r"^GOLDEN SPOON"),
    ("85°C Bakery Cafe", r"^85 ?C\b|^85 DEGREES"), ("Porto's Bakery", r"^PORTOS"), ("Paris Baguette", r"^PARIS BAGUETTE"),
    ("Tous les Jours", r"^TOUS LES JOURS"), ("Winchell's Donuts", r"^WINCHELLS"), ("Yum Yum Donuts", r"^YUM YUM DONUT"),
    ("Sharetea", r"^SHARETEA"), ("Gong Cha", r"^GONG CHA"), ("Kung Fu Tea", r"^KUNG FU TEA"), ("7 Leaves Cafe", r"^7 LEAVES"),
    ("Boba Guys", r"^BOBA GUYS"), ("Tapioca Express", r"^TAPIOCA EXPRESS"), ("Tastea", r"^TASTEA"), ("Ding Tea", r"^DING TEA"),
    ("Chatime", r"^CHATIME"), ("Tea Station", r"^TEA STATION"), ("Quickly", r"^QUICKLY$"), ("Omomo Tea Shoppe", r"^OMOMO"),
    ("Jollibee", r"^JOLLIBEE"), ("Chowking", r"^CHOW ?KING"), ("Goldilocks", r"^GOLDILOCKS"), ("Max's Restaurant", r"^MAXS (?:OF MANILA|RESTAURANT)"),
    ("L&L Hawaiian Barbecue", r"^L AND L (?:HAWAIIAN|DRIVE)|^L AND L$"), ("Ono Hawaiian BBQ", r"^ONO HAWAIIAN"),
    ("Juice It Up!", r"^JUICE IT UP"), ("Nekter Juice Bar", r"^NEKTER"), ("Pressed", r"^PRESSED(?: JUICERY)?$"), ("Robeks", r"^ROBEKS"),
    ("Blenders in the Grass", r"^BLENDERS IN THE GRASS"), ("Peach Wave", r"^PEACH WAVE"),
    ("Togo's", r"^TOGOS"), ("Port of Subs", r"^PORT OF SUBS"), ("Which Wich", r"^WHICH WICH"), ("Jersey Mike's", r"^JERSEY MIKE"),
    ("Cafe Rio", r"^CAFE RIO"), ("Costa Vida", r"^COSTA VIDA"), ("Rubio's Coastal Grill", r"^RUBIOS COASTAL"),
    ("Roberto's Taco Shop", r"^ROBERTOS (?:TACO|MEXICAN)"), ("Albertacos", r"^ALBERTACOS"), ("Taco Cabana", r"^TACO CABANA"),
    ("Burgerim", r"^BURGERIM"), ("The Halal Guys", r"^(?:THE )?HALAL GUYS"), ("Wingstop", r"^WINGSTOP"),
    ("Hash House A Go Go", r"^HASH HOUSE A GO GO"), ("Snooze", r"^SNOOZE"), ("Eggs n Things", r"^EGGS N THINGS"),
    ("Shari's", r"^SHARIS"), ("Elmer's", r"^ELMERS RESTAURANT"), ("Squeeze Inn", r"^SQUEEZE INN"),
    ("Mo' Bettahs", r"^MO BETTAHS"), ("Bubbakoo's Burritos", r"^BUBBAKOO"), ("Pancheros", r"^PANCHEROS"),
    ("Philly's Best", r"^PHILLYS BEST"), ("Mendocino Farms", r"^MENDOCINO FARMS"), ("Taco John's", r"^TACO JOHN"),
    ("Habit Burger Grill", r"^HABIT BURGER"), ("Slater's 50/50", r"^SLATERS 50"), ("Lucille's Smokehouse Bar-B-Que", r"^LUCILLES"),
    ("Ruth's Chris", r"^RUTHS CHRIS"), ("Mastro's", r"^MASTROS"), ("The Capital Grille", r"^(?:THE )?CAPITAL GRILLE"),
    ("Fleming's", r"^FLEMINGS"), ("Cheesecake Factory", r"^(?:THE )?CHEESECAKE FACTORY"), ("Grand Lux Cafe", r"^GRAND LUX"),
    ("Panda Express", r"^PANDA EXPRESS"), ("Chipotle", r"^CHIPOTLE"),
    # gas station and grocery counters (hidden with the non-restaurants)
    ("7-Eleven", r"^7 ELEVEN"), ("Circle K", r"^CIRCLE K"), ("AM/PM", r"^AM ?PM$|^ARCO AM ?PM"), ("Hunt Brothers Pizza", r"^HUNT BROTHERS"),
    ("Krispy Krunchy Chicken", r"^KRISPY KRUNCHY"), ("Chester's Chicken", r"^CHESTERS (?:FRIED )?CHICKEN"), ("Farmer's Fridge", r"^FARMERS FRIDGE"),
    ("MrBeast Burger", r"^MR ?BEAST"), ("It's Just Wings", r"^ITS JUST WINGS"), ("Wow Bao", r"^WOW BAO"),
]
_seen = set()
BRANDS = [(b, p) for b, p in BRANDS if not ((b, p) in _seen or _seen.add((b, p)))]
_C = [(b, re.compile(p)) for b, p in BRANDS]

# distinctive brands also recognized mid-name ("SAII BABA DUNKIN", "STARBUCKS INSIDE TARGET")
_ANYWHERE = [(b, re.compile(p)) for b, p in [("McDonald's", r"\bMC ?DONALDS\b"), ("Dunkin'", r"\bDUNKIN\b"), ("Starbucks", r"\bSTARBUCKS\b"),
             ("Wingstop", r"\bWING ?STOP\b"), ("Popeyes", r"\bPOPEYES\b"), ("Chipotle", r"\bCHIPOTLE\b"),
             ("Jimmy John's", r"\bJIMMY JOHNS\b"), ("Taco Bell", r"\bTACO BELL\b"), ("In-N-Out Burger", r"\bIN N OUT BURGER\b"),
             ("Jack in the Box", r"\bJACK IN THE BOX\b"), ("Panda Express", r"\bPANDA EXPRESS\b")]]


def brand_of(nkey, *more):
    """Brand from the display name, else from Overture's brand label."""
    keys = [k for k in [nkey] + [m for m in more if isinstance(m, str)] if isinstance(k, str)]
    for k in keys:
        for part in [k or ""] + [p.strip() for p in (k or "").split("/")]:
            for b, p in _C:
                if p.search(part):
                    return b
    for k in keys:
        for b, p in _ANYWHERE:
            if p.search(k or ""):
                return b
    return None
