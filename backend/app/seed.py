"""GramShiksha seed — idempotent (additive), trilingual, realistic.

Demo accounts (password shown / used at login):
  admin@gramshiksha.in      Admin@1234   (platform_admin)
  school@gramshiksha.in     School@1234  (school_admin, Zilla Parishad School)
  teacher1@gramshiksha.in   Teach@1234   (Sunita Devi, Math/Science)
  teacher2@gramshiksha.in   Teach@1234   (Rahul Patil, English/Languages)
  student1@gramshiksha.in   Learn@1234   (Arjun Kumar, Class 8, Maharashtra SSC, marathi)
  student2@gramshiksha.in   Learn@1234   (Priya Sharma, Class 10, CBSE)
  parent1@gramshiksha.in    Parent@1234  (linked to student1)

Content: 9 courses (Class 1-12), 20+ chapters, 25+ lessons (rich Marathi & Hindi),
70-question trilingual bank (mcq/truefalse/multi/fill) across subjects & difficulties,
official textbook links, demo doubts/notifications/materials.
"""
import json
import random

from sqlmodel import Session, select

from .gamification import seed_badges
from .models import (BadgeDef, Board, Chapter, Course, DailyActivity, Doubt, DoubtReply,
                     Enrollment, Lesson, Notification, Question, Quiz, QuizQuestion, School,
                     Subject, Textbook, User, QuizAttempt, PracticeAttempt, TopicStats)
from .models import Material
from .security import hash_password

BOARDS = ["Maharashtra SSC", "Maharashtra HSC", "CBSE"]

# Subjects per class band — name triples (en, hi, mr)
SUBJECTS_PRIMARY = [  # classes 1-5
    ("Mathematics", "गणित", "गणित"),
    ("English", "अंग्रेज़ी", "इंग्रजी"),
    ("Hindi", "हिंदी", "हिंदी"),
    ("Marathi", "मराठी", "मराठी"),
    ("Environmental Studies", "पर्यावरण अध्ययन", "पर्यावरण अभ्यास"),
]
SUBJECTS_MIDDLE = [  # 6-8
    ("Mathematics", "गणित", "गणित"),
    ("Science", "विज्ञान", "विज्ञान"),
    ("English", "अंग्रेज़ी", "इंग्रजी"),
    ("Hindi", "हिंदी", "हिंदी"),
    ("Marathi", "मराठी", "मराठी"),
    ("Social Science", "सामाजिक विज्ञान", "सामाजिक शास्त्र"),
]
SUBJECTS_SECONDARY = [  # 9-10
    ("Mathematics", "गणित", "गणित"),
    ("Science", "विज्ञान", "विज्ञान"),
    ("English", "अंग्रेज़ी", "इंग्रजी"),
    ("Hindi", "हिंदी", "हिंदी"),
    ("Marathi", "मराठी", "मराठी"),
    ("History", "इतिहास", "इतिहास"),
    ("Geography", "भूगोल", "भूगोल"),
]
SUBJECTS_HSC = [  # 11-12
    ("Physics", "भौतिक विज्ञान", "भौतिकशास्त्र"),
    ("Chemistry", "रसायन विज्ञान", "रसायनशास्त्र"),
    ("Biology", "जीव विज्ञान", "जीवशास्त्र"),
    ("Mathematics", "गणित", "गणित"),
    ("Computer Science", "कंप्यूटर विज्ञान", "संगणक शास्त्र"),
    ("English", "अंग्रेज़ी", "इंग्रजी"),
]

COURSES = [
    # (slug, class, board, subject, lang, titles en/hi/mr, difficulty, duration)
    ("g8-ssc-science-course", 8, "Maharashtra SSC", "Science", "mr",
     ("Science — Class 8 (SSC)", "विज्ञान — कक्षा 8 (SSC)", "विज्ञान — इयत्ता ८ (एसएससी)"),
     "medium", 240),
    ("g8-ssc-math-course", 8, "Maharashtra SSC", "Mathematics", "mr",
     ("Mathematics — Class 8 (SSC)", "गणित — कक्षा 8 (SSC)", "गणित — इयत्ता ८ (एसएससी)"),
     "medium", 260),
    ("g10-cbse-science-course", 10, "CBSE", "Science", "hi",
     ("Science — Class 10 (CBSE)", "विज्ञान — कक्षा 10 (CBSE)", "विज्ञान — इयत्ता १० (सीबीएसई)"),
     "medium", 320),
    ("g10-cbse-math-course", 10, "CBSE", "Mathematics", "hi",
     ("Mathematics — Class 10 (CBSE)", "गणित — कक्षा 10 (CBSE)", "गणित — इयत्ता १० (सीबीएसई)"),
     "hard", 340),
    ("g5-ssc-marathi-course", 5, "Maharashtra SSC", "Marathi", "mr",
     ("Marathi — Class 5 (SSC)", "मराठी — कक्षा 5 (SSC)", "मराठी — इयत्ता ५ (एसएससी)"),
     "easy", 120),
    ("g6-ssc-marathi-course", 6, "Maharashtra SSC", "Marathi", "mr",
     ("Marathi — Class 6 (SSC)", "मराठी — कक्षा 6 (SSC)", "मराठी — इयत्ता ६ (एसएससी)"),
     "easy", 140),
    ("g7-ssc-hindi-course", 7, "Maharashtra SSC", "Hindi", "hi",
     ("Hindi — Class 7 (SSC)", "हिंदी — कक्षा 7 (SSC)", "हिंदी — इयत्ता ७ (एसएससी)"),
     "easy", 150),
    ("g1-ssc-math-course", 1, "Maharashtra SSC", "Mathematics", "mr",
     ("Math Fun — Class 1", "गणित मज़ेदार — कक्षा 1", "गणित मजेदार — इयत्ता १"),
     "easy", 80),
    ("g12-hsc-physics-course", 12, "Maharashtra HSC", "Physics", "en",
     ("Physics — Class 12 (HSC)", "भौतिकी — कक्षा 12 (HSC)", "भौतिकशास्त्र — इयत्ता १२ (एचएससी)"),
     "hard", 400),
]

# Chapters per course: (title triple, lessons[(title triple, type, minutes, body_en, body_hi, body_mr)])
COURSE_CONTENT = {
    "g8-ssc-science-course": [
        (("Living World", "जीव जगत", "जीवन सृष्टि"), [
            (("Introduction to Cells", "कोशिका का परिचय", "पेशीची ओळख"), "text", 12,
             "All living things are made of cells. A cell is the smallest unit of life. "
             "Plants, animals and humans — all are built from cells. Some organisms like "
             "bacteria have just one cell!",
             "सभी जीव कोशिकाओं से बने हैं। कोशिका जीवन की सबसे छोटी इकाई है। पौधे, जानवर और इंसान — सभी कोशिकाओं से बने हैं। बैक्टीरिया जैसे जीवों में केवल एक कोशिका होती है!",
             "सर्व सजीव पेशींपासून बनलेले असतात. पेशी ही जीवनाची सर्वात लहान एकक आहे. वनस्पती, प्राणी आणि माणसे — सर्व पेशींपासून बनलेली असतात. बॅक्टेरियासारख्या जीवांमध्ये फक्त एकच पेशी असते!"),
            (("Cell Structure", "कोशिका संरचना", "पेशी रचना"), "video", 15,
             "A cell has a nucleus (control center), cytoplasm (jelly) and cell membrane (cover). "
             "Plant cells also have a cell wall and chloroplasts for making food.",
             "कोशिका में न्यूक्लियस (नियंत्रण केंद्र), साइटोप्लाज्म (जेली) और कोशिका झिल्ली (आवरण) होते हैं। पादप कोशिका में कोशिका भित्ति और हरितलवक भी होते हैं।",
             "पेशीमध्ये केंद्रक (नियंत्रण केंद्र), साइटोप्लाझम (जिली) आणि पेशीपटल (आवरण) असते. वनस्पती पेशीमध्ये पेशीभित्ती आणि हरितकण असतात."),
        ]),
        (("Force and Pressure", "बल और दाब", "बल आणि दाब"), [
            (("What is Force?", "बल क्या है?", "बल म्हणजे काय?"), "text", 10,
             "A force is a push or a pull. Opening a door, kicking a ball, lifting a bag — "
             "all use force. Force can change speed, direction or shape of objects. "
             "It is measured in newtons (N).",
             "बल धक्का या खिंचाव है। दरवाज़ा खोलना, गेंद लात मारना, बैग उठाना — सभी में बल लगता है। बल गति, दिशा या आकार बदल सकता है। इसे न्यूटन (N) में मापते हैं।",
             "बल म्हणजे ढकलणे किंवा ओढणे. दार उघडणे, चेंडूला लाथ मारणे, बॅग उचलणे — सर्वात बल लागते. बल वेग, दिशा किंवा आकार बदलू शकतो. तो न्यूटन (N) मध्ये मोजला जातो."),
            (("Pressure in Daily Life", "रोज़मर्रा की ज़िंदगी में दाब", "रोजंदार जीवनातील दाब"), "text", 10,
             "Pressure = force ÷ area. A sharp knife cuts better because its small area gives "
             "high pressure. Wide straps on school bags feel comfortable because they spread "
             "the force over a larger area.",
             "दाब = बल ÷ क्षेत्रफल। नुकीली छुरी बेहतर काटती है क्योंकि छोटे क्षेत्र पर दाब ज़्यादा होता है। बस्ते की चौड़ी पट्टियाँ आरामदायक होती हैं क्योंकि वे बल फैला देती हैं।",
             "दाब = बल ÷ क्षेत्रफळ. टोकदार चाकू चांगला आपटतो कारण लहान क्षेत्रावर दाब जास्त असतो. बॅगच्या रुंद पट्ट्या आरामदायी असतात कारण त्या बल पसरवतात."),
        ]),
        (("States of Matter", "पदार्थ की अवस्थाएँ", "पदार्थाच्या अवस्था"), [
            (("Solid, Liquid, Gas", "ठोस, द्रव, गैस", "घन, द्रव, वायू"), "text", 12,
             "Matter has three main states: solid (fixed shape), liquid (flows, takes the "
             "container's shape), gas (spreads everywhere). Ice, water and steam are the same "
             "substance in three states. Heating changes state.",
             "पदार्थ की तीन मुख्य अवस्थाएँ: ठोस (निश्चित आकार), द्रव (बहता है), गैस (फैलती है)। बर्फ, पानी और भाप एक ही पदार्थ की तीन अवस्थाएँ हैं। गर्मी से अवस्था बदलती है।",
             "पदार्थाच्या तीन मुख्य अवस्था: घन (निश्चित आकार), द्रव (वाहतो), वायू (पसरतो). बर्फ, पाणी आणि वाफ ही एकाच पदार्थाच्या तीन अवस्था आहेत. उष्णतेमुळे अवस्था बदलते."),
        ]),
    ],
    "g8-ssc-math-course": [
        (("Rational Numbers", "परिमेय संख्याएँ", "परिमेय संख्या"), [
            (("Understanding Fractions", "भिन्न समझना", "अपूर्णांक समजून घेणे"), "text", 15,
             "A fraction shows parts of a whole. 3/4 means 3 parts out of 4 equal parts. "
             "Like fractions have the same denominator (1/5, 2/5); unlike fractions do not "
             "(1/2, 3/4). To compare, convert to the same denominator.",
             "भिन्न पूर्ण के भाग दिखाती है। 3/4 का मतलब 4 बराबर भागों में से 3। समान हर वाली भिन्नें (1/5, 2/5); असमान हर वाली (1/2, 3/4)। तुलना के लिए हर समान करें।",
             "अपूर्णांक संपूर्णाचे भाग दाखवतो. ३/४ म्हणजे ४ समान भागांपैकी ३ भाग. समान छेद असलेले अपूर्णांक (१/५, २/५); भिन्न छेद असलेले (१/२, ३/४). तुलना करण्यासाठी छेद समान करा."),
        ]),
        (("Linear Equations", "रैखिक समीकरण", "रेषीय समीकरण"), [
            (("Solving One-Variable Equations", "एक चर समीकरण हल करना", "एकचल समीकरण सोडवणे"), "text", 16,
             "Solve x + 5 = 12 by subtracting 5 from both sides: x = 7. Always do the same "
             "operation on both sides. Check: 7 + 5 = 12 ✓",
             "x + 5 = 12 को दोनों ओर से 5 घटाकर हल करें: x = 7। दोनों ओर एक ही काम करें। जाँच: 7 + 5 = 12 ✓",
             "x + 5 = 12 सोडवण्यासाठी दोन्ही बाजूंनून ५ वजा करा: x = 7. दोन्ही बाजूंवर एकच क्रिया करा. तपासा: ७ + ५ = १२ ✓"),
        ]),
        (("Percentage", "प्रतिशत", "टक्केवारी"), [
            (("Understanding Percentage", "प्रतिशत समझना", "टक्केवारी समजून घेणे"), "text", 14,
             "Percent means 'per hundred'. 50% = 50/100 = half. To find 25% of 80: "
             "80 × 25/100 = 20. Discounts, exam marks and cricket strike rates all use "
             "percentages.",
             "प्रतिशत का मतलब 'प्रति सौ'। 50% = 50/100 = आधा। 80 का 25% निकालने के लिए: 80 × 25/100 = 20। छूट, परीक्षा के अंक और क्रिकेट स्ट्राइक रेट — सब प्रतिशत में।",
             "टक्केवारी म्हणजे 'शंभराला किती'. ५०% = ५०/१०० = अर्धा. ८० च्या २५% काढण्यासाठी: ८० × २५/१०० = २०. सवलती, परीक्षेतील गुण आणि क्रिकेटचे स्ट्राइक रेट — सर्व टक्केवारीत."),
        ]),
    ],
    "g10-cbse-science-course": [
        (("Chemical Reactions", "रासायनिक अभिक्रियाएँ", "रासायनिक अभिक्रिया"), [
            (("Balancing Equations", "समीकरण संतुलन", "समीकरण संतुलन"), "text", 18,
             "A chemical equation must be balanced: same number of atoms of each element on "
             "both sides. Example: 2H₂ + O₂ → 2H₂O. Count atoms: left 4H, 2O; right 4H, 2O. "
             "Balanced! Practice by counting atoms first, then adjust coefficients.",
             "रासायनिक समीकरण संतुलित होना चाहिए: दोनों ओर प्रत्येक तत्व के समान परमाणु। उदाहरण: 2H₂ + O₂ → 2H₂O। बाईं ओर 4H, 2O; दाईं ओर 4H, 2O। संतुलित! पहले परमाणु गिनें, फिर गुणांक बदलें।",
             "रासायनिक समीकरण संतुलित असणे आवश्यक आहे: दोन्ही बाजूंना प्रत्येक मूलद्रव्याचे समान अणू. उदाहरण: 2H₂ + O₂ → 2H₂O. डावीकडे 4H, 2O; उजवीकडे 4H, 2O. संतुलित! आधी अणू मोजा, नंतर गुणांक बदला."),
            (("Types of Reactions", "अभिक्रिया के प्रकार", "अभिक्रियांचे प्रकार"), "video", 20,
             "Combination: A+B→AB. Decomposition: AB→A+B. Displacement: A+BC→AC+B. "
             "Rusting of iron is slow oxidation; burning of magnesium is fast combination.",
             "संयोग: A+B→AB। अपघटन: AB→A+B। विस्थापन: A+BC→AC+B। लोहे में जंग धीमी ऑक्सीकरण है; मैग्नीशियम का दहन तेज़ संयोग है।",
             "एकीकरण: A+B→AB. विघटन: AB→A+B. विस्थापन: A+BC→AC+B. लोखंडाला गंज हळू ऑक्सिडेशन आहे; मॅग्नेशियमचे दहन जलद एकीकरण आहे."),
        ]),
        (("Acids, Bases and Salts", "अम्ल, क्षार और लवण", "आम्ल, क्षार आणि मीठ"), [
            (("Understanding pH", "pH समझना", "पीएच समजून घेणे"), "text", 15,
             "Acids taste sour, bases feel slippery. The pH scale runs 0–14: below 7 acidic, "
             "7 neutral, above 7 basic. Lemon juice ≈ 2, pure water = 7, soap ≈ 10. "
             "Soil pH decides which crops grow best.",
             "अम्ल खट्टे होते हैं, क्षार फिसलने। pH स्केल 0–14: 7 से कम अम्लीय, 7 उदासीन, 7 से ऊपर क्षारीय। नींबू रस ≈ 2, शुद्ध पानी = 7, साबुन ≈ 10। मिट्टी का pH फसल तय करता है।",
             "आम्लांचा आंबट रस, क्षार घसरगोंड. पीएच श्रेणी ०–१४: ७ पेक्षा कमी आम्लीय, ७ तटस्थ, ७ पेक्षा जास्त क्षारीय. लिंबू रस ≈ २, शुद्ध पाणी = ७, साबण ≈ १०. जमिनीचा पीएच पीक ठरवतो."),
        ]),
    ],
    "g10-cbse-math-course": [
        (("Linear Equations", "दो चर वाले रैखिक समीकरण", "रेषीय समीकरणे"), [
            (("Pair of Linear Equations", "रैखिक समीकरण युग्म", "रेषीय समीकरण जोडी"), "text", 18,
             "Two equations, two variables: x + y = 10 and x − y = 2. Add them: 2x = 12, "
             "so x = 6, y = 4. Graphically each equation is a line; the solution is where "
             "the lines cross.",
             "दो समीकरण, दो चर: x + y = 10 और x − y = 2। जोड़ें: 2x = 12, इसलिए x = 6, y = 4। ग्राफ़ में हर समीकरण एक रेखा है; हल वहाँ है जहाँ रेखाएँ काटती हैं।",
             "दोन समीकरणे, दोन चले: x + y = 10 आणि x − y = 2. बेरीज करा: 2x = 12, म्हणजे x = ६, y = ४. आलेखात प्रत्येक समीकरण एक रेषा; उत्तर म्हणजे रेषा छेदत तो बिंदू."),
        ]),
        (("Quadratic Equations", "द्विघात समीकरण", "वर्ग समीकरणे"), [
            (("Solving x² = 9", "x² = 9 हल करना", "x² = 9 सोडवणे"), "text", 16,
             "A quadratic equation has x². Example: x² − 9 = 0 → x² = 9 → x = ±3. "
             "Factor when possible: x² − 5x + 6 = 0 → (x−2)(x−3) = 0 → x = 2 or 3.",
             "द्विघात समीकरण में x² होता है। उदाहरण: x² − 9 = 0 → x² = 9 → x = ±3। गुणनखंड से: x² − 5x + 6 = 0 → (x−2)(x−3) = 0 → x = 2 या 3।",
             "वर्ग समीकरणात x² असते. उदा.: x² − 9 = 0 → x² = 9 → x = ±३. अवयव पाडता येते: x² − 5x + 6 = 0 → (x−2)(x−3) = 0 → x = २ किंवा ३."),
        ]),
    ],
    "g5-ssc-marathi-course": [
        (("मुलाखती व निवेदन", "साधी वाक्ये", "साधी वाक्ये"), [
            (("वाचन सराव", "वाक्य रचना", "वाक्य रचना"), "text", 10,
             "Simple sentences in Marathi: मी शाळेत जातो. (I go to school.) ती पुस्तक वाचते. "
             "(She reads a book.) Practice reading aloud daily.",
             "मराठी में सरल वाक्य: मी शाळेत जातो। ती पुस्तक वाचते। रोज़ ज़ोर से पढ़ने का अभ्यास करें।",
             "मराठीत साधी वाक्ये: मी शाळेत जातो. ती पुस्तक वाचते. रोज मोठ्याने वाचण्याचा सराव करा."),
        ]),
        (("वाचन व निबंध", "पढ़ना और निबंध", "वाचन व निबंध"), [
            (("माझी शाळा (निबंध)", "मेरा स्कूल (निबंध)", "माझी शाळा (निबंध)"), "text", 12,
             "Essay example in Marathi: 'माझी शाळा गावात आहे. शाळेत दहा खोल्या आहेत. माझी "
             "शिक्षिका सुनिता ताई आम्हाला छान शिकवतात.' Short essays like this build writing skills.",
             "मराठी निबंध का उदाहरण: 'माझी शाळा गावात आहे। शाळेत दहा खोल्या आहेत।' ऐसे छोटे निबंध लेखन कौशल बढ़ाते हैं।",
             "निबंधाचे उदाहरण: 'माझी शाळा गावात आहे. शाळेत दहा खोल्या आहेत. माझी शिक्षिका सुनिता ताई आम्हाला छान शिकवतात. शाळेच्या मागे आम्ही खेळतो.' लहान निबंधांनी लेखन कौशल्य वाढते."),
        ]),
    ],
    "g6-ssc-marathi-course": [
        (("कविता आनंद", "कविता का आनंद", "कविता आनंद"), [
            (("माझे गाव (कविता)", "मेरा गाँव (कविता)", "माझे गाव (कविता)"), "text", 10,
             "A simple Marathi poem about my village: 'माझे गाव सुंदर, हिरवे गार; शेतात भरभराटीचे धान्याचे सार'. "
             "Poems teach rhythm and new words. Read aloud twice daily.",
             "'माझे गाव सुंदर, हिरवे गार...' — मेरे गाँव पर सरल मराठी कविता। कविता से लय और नए शब्द मिलते हैं। रोज़ दो बार ज़ोर से पढ़ें।",
             "'माझे गाव सुंदर, हिरवे गार; शेतात भरभराटीचे धान्याचे सार' — गावावरील सोपी मराठी कविता. कवितेमुळे लय आणि नवीन शब्द शिकायला मिळतात. रोज दोनदा मोठ्याने वाचा."),
        ]),
        (("व्याकरण", "व्याकरण", "व्याकरण"), [
            (("नाम आणि सर्वनाम", "संज्ञा और सर्वनाम", "नाम आणि सर्वनाम"), "text", 12,
             "Nouns name people, places or things: शाळा, पुस्तक, आई. Pronouns replace nouns: "
             "मी, तू, तो, ती. Example: 'राम शाळेत जातो' → 'तो शाळेत जातो'.",
             "संज्ञा किसी के नाम का बोध कराती है: शाळा, पुस्तक, आई। सर्वनाम संज्ञा की जगह लेते हैं: मी, तू, तो, ती। जैसे: 'राम शाळेत जातो' → 'तो शाळेत जातो'।",
             "नाम म्हणजे व्यक्ती, ठिकाण यांचे नाव: शाळा, पुस्तक, आई. सर्वनामे नामाऐवजी येतात: मी, तू, तो, ती. उदा. 'राम शाळेत जातो' → 'तो शाळेत जातो'."),
        ]),
    ],
    "g7-ssc-hindi-course": [
        (("कहानी की दुनिया", "गोष्टींचे जग", "कहानी की दुनिया"), [
            (("ईमानदार लकड़हारा", "प्रामाणिक सुतार", "ईमानदार लकड़हारा"), "text", 12,
             "A woodcutter dropped his axe in the river. The river goddess showed a golden axe, "
             "then a silver axe — he said 'no, that is not mine'. Pleased by his honesty, she "
             "gave him all three. Moral: honesty is the best policy.",
             "एक लकड़हारे की कुल्हाड़ी नदी में गिर गई। जलदेवी ने सोने की कुल्हाड़ी दिखाई, फिर चाँदी की — उसने कहा 'नहीं, यह मेरी नहीं'। ईमानदारी से खुश होकर देवी ने तीनों दे दीं। सीख: ईमानदारी सबसे अच्छा गुण है।",
             "एका सुताराची कुरहाड नदीत पडली. नदीदेवीने सोन्याची कुरहाड दाखवली, मग चांदीची — त्याने म्हटले 'नाही, ही माझी नाही'. प्रामाणिकपणाने प्रसन्न होऊन देवीने तिन्ही दिल्या. धडा: प्रामाणिकपणा हाच उत्तम गुण."),
        ]),
        (("व्याकरण", "व्याकरण", "व्याकरण"), [
            (("संज्ञा और वचन", "नाम आणि वचन", "संज्ञा और वचन"), "text", 10,
             "Hindi nouns have singular and plural (वचन): लड़का → लड़के, किताब → किताबें. "
             "The verb must match: 'लड़का पढ़ता है', 'लड़के पढ़ते हैं'.",
             "हिंदी में संज्ञाओं के एकवचन और बहुवचन होते हैं: लड़का → लड़के, किताब → किताबें। क्रिया वचन से मिलाती है: 'लड़का पढ़ता है', 'लड़के पढ़ते हैं'।",
             "हिंदीत नामांचे एकवचन आणि अनेकवचन असते: लड़का → लड़के, किताब → किताबें. क्रियापद वचनाशी जुळते: 'लड़का पढ़ता है', 'लड़के पढ़ते हैं'."),
        ]),
    ],
    "g1-ssc-math-course": [
        (("Numbers 1-20", "संख्या 1-20", "संख्या १-२०"), [
            (("Counting Fun", "गिनती का मज़ा", "मोजण्याचा आनंद"), "text", 8,
             "Count objects around you: 1 एक, 2 दोन, 3 तीन... Count mangoes, stones, steps. "
             "Counting every day makes numbers easy!",
             "अपने आस-पास की चीज़ें गिनें: 1 एक, 2 दो, 3 तीन... आम, पत्थर, सीढ़ियाँ गिनें। रोज़ गिनती से गणित आसान होता है!",
             "तुमच्या आसपासच्या वस्तू मोजा: १ एक, २ दोन, ३ तीन... आंबे, दगड, पायऱ्या मोजा. रोज मोजण्याने अंक सोपे होतात!"),
        ]),
        (("आकार", "आकृतियाँ", "आकार"), [
            (("Circle, Triangle, Square", "गोला, त्रिकोण, चौकोन", "वर्तुळ, त्रिकोण, चौकोन"), "text", 8,
             "Shapes are everywhere! A ball is round (गोल), roti is a circle, samosa is a "
             "triangle (त्रिकोण), window is a square (चौकोन). Count sides: triangle 3, square 4.",
             "आकृतियाँ हर जगह हैं! गेंद गोल है, रोटी गोल, समोसा त्रिकोण, खिड़की चौकोन। भुजाएँ गिनें: त्रिकोण 3, चौकोन 4।",
             "आकार सर्वत्र आहेत! चेंडू गोल, पोळी गोल, समोसा त्रिकोण, खिडकी चौकोन. बाजू मोजा: त्रिकोण ३, चौकोन ४."),
        ]),
    ],
    "g12-hsc-physics-course": [
        (("Electrostatics", "स्थिर वैद्युतिकी", "स्थिर विद्युत"), [
            (("Coulomb's Law", "कूलॉम का नियम", "कूलॉम्बचा नियम"), "text", 20,
             "F = k·q₁q₂/r². The force between two charges is proportional to the product of "
             "charges and inversely proportional to the square of distance. k = 9×10⁹ N·m²/C².",
             "F = k·q₁q₂/r²। दो आवेशों के बीच बल आवेशों के गुणनफल के समानुपाती और दूरी के वर्ग के व्युत्क्रमानुपाती होता है। k = 9×10⁹ N·m²/C²।",
             "F = k·q₁q₂/r². दोन आवेशांमधील बल आवेशांच्या गुणाकाराच्या प्रमाणात आणि अंतराच्या वर्गाच्या व्यस्तप्रमाणात असतो. k = ९×१०⁹ N·m²/C²."),
        ]),
        (("Motion", "गति", "गती"), [
            (("Newton's Laws", "न्यूटन के नियम", "न्यूटनचे नियम"), "text", 18,
             "First law: objects keep their state (rest/motion) unless a force acts — inertia. "
             "Second law: F = ma. Third law: every action has an equal and opposite reaction. "
             "Rockets work on the third law.",
             "पहला नियम: वस्तुएँ अपनी अवस्था बनाए रखती हैं जब तक बल न लगे — जड़त्व। दूसरा: F = ma। तीसरा: हर क्रिया की बराबर व विपरीत प्रतिक्रिया। रॉकेट तीसरे नियम पर काम करता है।",
             "पहला नियम: वस्तू स्वतःची अवस्था टिकवून ठेवते जोपर्यंत बल न लागे — जडत्व. दुसरा: F = ma. तिसरा: प्रत्येक क्रियेला समान व विरुद्ध प्रतिक्रिया. रॉकेट तिसऱ्या नियमावर काम करते."),
        ]),
    ],
}

# Question bank: (subject, topic, difficulty, type, prompt×3, options×3, correct, explanation×3)
# 70 questions · Class 1-12 · mcq / truefalse / multi / fill · easy/medium/hard
QUESTIONS = [
    # ---- Mathematics: primary (Class 1-5) ----
    ("Mathematics", "counting", "easy", "mcq",
     ("Which number comes right after 7?", "7 के ठीक बाद कौन सी संख्या आती है?", "७ च्या नंतर कोणती संख्या येते?"),
     (["8", "6", "9", "10"], ["8", "6", "9", "10"], ["८", "६", "९", "१०"]),
     0,
     ("Count: 5, 6, 7, 8 — 8 comes after 7.", "गिनती: 5, 6, 7, 8 — 7 के बाद 8 आता है।", "मोजा: ५, ६, ७, ८ — ७ नंतर ८ येते.")),
    ("Mathematics", "counting", "easy", "fill",
     ("2 + 3 = ____ (write as a number)", "2 + 3 = ____ (संख्या में लिखें)", "२ + ३ = ____ (अंकी लिहा)"),
     ([], [], []),
     "5",
     ("Start at 2, count 3 more: 3, 4, 5.", "2 से शुरू कर 3 और गिनो: 3, 4, 5।", "२ पासून ३ अजून मोजा: ३, ४, ५.")),
    ("Mathematics", "addition", "easy", "mcq",
     ("What is 5 + 4?", "5 + 4 कितना है?", "५ + ४ किती?"),
     (["9", "8", "10", "7"], ["9", "8", "10", "7"], ["९", "८", "१०", "७"]),
     0,
     ("5 fingers + 4 fingers = 9 fingers.", "5 उंगलियाँ + 4 उंगलियाँ = 9।", "५ बोटे + ४ बोटे = ९.")),
    ("Mathematics", "subtraction", "easy", "mcq",
     ("What is 9 − 4?", "9 − 4 कितना है?", "९ − ४ किती?"),
     (["5", "4", "6", "3"], ["5", "4", "6", "3"], ["५", "४", "६", "३"]),
     0,
     ("Take 4 away from 9 — 5 remain.", "9 में से 4 निकालो — 5 बचे।", "९ मधून ४ काढा — ५ उरतात.")),
    ("Mathematics", "shapes", "easy", "mcq",
     ("How many sides does a triangle have?", "त्रिभुज की कितनी भुजाएँ होती हैं?", "त्रिकोणाला किती बाजू असतात?"),
     (["3", "4", "5", "6"], ["3", "4", "5", "6"], ["३", "४", "५", "६"]),
     0,
     ("'Tri' means three — a triangle has 3 sides.", "'त्रि' का मतलब तीन — त्रिभुज की 3 भुजाएँ।", "'त्रि' म्हणजे तीन — त्रिकोणाला ३ बाजू.")),
    ("Mathematics", "shapes", "easy", "truefalse",
     ("A square has 4 equal sides.", "एक वर्ग की 4 बराबर भुजाएँ होती हैं।", "चौकोनाला ४ समान बाजू असतात."),
     (["True", "False"], ["सही", "गलत"], ["बरोबर", "चूक"]),
     0,
     ("All four sides of a square are equal.", "वर्ग की चारों भुजाएँ बराबर होती हैं।", "चौकोनाच्या चारही बाजू समान असतात.")),
    ("Mathematics", "multiplication", "medium", "mcq",
     ("What is 6 × 3?", "6 × 3 कितना है?", "६ × ३ किती?"),
     (["18", "12", "16", "15"], ["18", "12", "16", "15"], ["१८", "१२", "१६", "१५"]),
     0,
     ("6 + 6 + 6 = 18.", "6 + 6 + 6 = 18।", "६ + ६ + ६ = १८.")),
    ("Mathematics", "multiplication", "medium", "mcq",
     ("Which is the same as 5 × 4?", "5 × 4 किसके बराबर है?", "५ × ४ च्या बरोबर काय?"),
     (["5+5+5+5", "5+4", "4×4", "5+5"], ["5+5+5+5", "5+4", "4×4", "5+5"], ["५+५+५+५", "५+४", "४×४", "५+५"]),
     0,
     ("5 × 4 means 4 groups of 5.", "5 × 4 = 5 के 4 समूह।", "५ × ४ म्हणजे ५ चे ४ गट.")),
    ("Mathematics", "time", "easy", "mcq",
     ("How many days are there in a week?", "एक सप्ताह में कितने दिन होते हैं?", "आठवड्यात किती दिवस असतात?"),
     (["7", "5", "10", "12"], ["7", "5", "10", "12"], ["७", "५", "१०", "१२"]),
     0,
     ("Monday to Sunday — 7 days.", "सोमवार से रविवार — 7 दिन।", "सोमवार ते रविवार — ७ दिवस.")),
    ("Mathematics", "money", "easy", "mcq",
     ("You have ₹10 and get ₹25 more. How much in total?", "आपके पास ₹10 हैं और ₹25 और मिले। कुल?", "तुमच्याकडे ₹१० आहेत आणि ₹२५ आणखी मिळाले. एकूण?"),
     (["₹35", "₹30", "₹40", "₹25"], ["₹35", "₹30", "₹40", "₹25"], ["₹३५", "₹३०", "₹४०", "₹२५"]),
     0,
     ("10 + 25 = 35 rupees.", "10 + 25 = 35 रुपये।", "१० + २५ = ३५ रुपये.")),
    # ---- Mathematics: middle (Class 6-8) ----
    ("Mathematics", "fractions", "easy", "mcq",
     ("Which fraction is the largest?", "कौन सी भिन्न सबसे बड़ी है?", "कोणता अपूर्णांक सर्वात मोठा?"),
     (["1/4", "1/2", "1/8"], ["1/4", "1/2", "1/8"], ["१/४", "१/२", "१/८"]),
     1,
     ("1/2 means half — bigger than 1/4 or 1/8 of the same whole.", "1/2 अर्थात आधा — उसी पूर्ण के 1/4 या 1/8 से बड़ा।", "१/२ म्हणजे अर्धा — त्याच संपूर्णाच्या १/४ किंवा १/८ पेक्षा मोठा.")),
    ("Mathematics", "fractions", "medium", "fill",
     ("1/2 + 1/2 = ____ (write as a number)", "1/2 + 1/2 = ____ (संख्या में लिखें)", "१/२ + १/२ = ____ (अंकी लिहा)"),
     ([], [], []),
     "1",
     ("Two halves make one whole.", "दो आधे एक पूर्ण बनाते हैं।", "दोन अर्धे एक संपूर्ण होतात.")),
    ("Mathematics", "fractions", "medium", "mcq",
     ("What is 2/3 + 1/3?", "2/3 + 1/3 कितना है?", "२/३ + १/३ किती?"),
     (["1", "2/6", "1/3", "2/3"], ["1", "2/6", "1/3", "2/3"], ["१", "२/६", "१/३", "२/३"]),
     0,
     ("Same denominator: add numerators 2+1 = 3 → 3/3 = 1.", "समान हर: अंश जोड़ो 2+1 = 3 → 3/3 = 1।", "समान छेद: अंश बेरजा २+१ = ३ → ३/३ = १.")),
    ("Mathematics", "fractions", "hard", "mcq",
     ("Which fraction is the smallest?", "कौन सी भिन्न सबसे छोटी है?", "कोणता अपूर्णांक सर्वात लहान?"),
     (["1/2", "3/4", "2/3", "5/6"], ["1/2", "3/4", "2/3", "5/6"], ["१/२", "३/४", "२/३", "५/६"]),
     0,
     ("Half (1/2) is the smallest of these fractions.", "आधा (1/2) इनमें सबसे छोटा है।", "अर्धा (१/२) यांतील सर्वात लहान.")),
    ("Mathematics", "linear_equations", "medium", "mcq",
     ("Solve: x + 7 = 15. x = ?", "हल करें: x + 7 = 15. x = ?", "सोडवा: x + 7 = 15. x = ?"),
     (["8", "6", "22", "7"], ["8", "6", "22", "7"], ["८", "६", "२२", "७"]),
     0,
     ("Subtract 7 from both sides: x = 15 − 7 = 8.", "दोनों ओर से 7 घटाएँ: x = 15 − 7 = 8।", "दोन्ही बाजूंनून ७ वजा करा: x = १५ − ७ = ८.")),
    ("Mathematics", "linear_equations", "medium", "mcq",
     ("If 3x = 12, then x = ?", "यदि 3x = 12, तो x = ?", "जर 3x = 12, तर x = ?"),
     (["4", "3", "6", "36"], ["4", "3", "6", "36"], ["४", "३", "६", "३६"]),
     0,
     ("Divide both sides by 3: x = 12/3 = 4.", "दोनों ओर को 3 से भाग दें: x = 4।", "दोन्ही बाजू ३ ने भागा: x = ४.")),
    ("Mathematics", "linear_equations", "hard", "multi",
     ("Which are solutions of 2x = 10? (select all)", "2x = 10 के हल कौन हैं? (सभी चुनें)", "2x = 10 चे उत्तरे कोणती? (सर्व निवडा)"),
     (["x=5", "x=10", "x=½×10"], ["x=5", "x=10", "x=½×10"], ["x=५", "x=१०", "x=½×१०"]),
     [0, 2],
     ("2×5=10 ✓; ½×10=5, 2×5=10 ✓; 2×10=20 ✗.", "2×5=10 ✓; ½×10=5 ✓; 2×10=20 ✗।", "२×५=१० ✓; ½×१०=५ ✓; २×१०=२० ✗.")),
    ("Mathematics", "geometry", "medium", "mcq",
     ("The sum of angles in a triangle is:", "त्रिभुज के कोणों का योग होता है:", "त्रिकोणाच्या कोनांची बेरीज:"),
     (["180°", "90°", "360°", "270°"], ["180°", "90°", "360°", "270°"], ["१८०°", "९०°", "३६०°", "२७०°"]),
     0,
     ("Always 180°, whatever the triangle's shape.", "हमेशा 180°, त्रिभुज किसी भी आकार का हो।", "नेहमी १८०°, त्रिकोण कोणताही असो.")),
    ("Mathematics", "geometry", "easy", "truefalse",
     ("A right angle measures 90°.", "समकोण 90° का होता है।", "समकोन ९०° असतो."),
     (["True", "False"], ["सही", "गलत"], ["बरोबर", "चूक"]),
     0,
     ("A right angle = exactly 90°, like a corner of a book.", "समकोण = ठीक 90°, जैसे किताब का कोना।", "समकोन = नेमका ९०°, पुस्तकाच्या कोपऱ्यासारखा.")),
    ("Mathematics", "percentage", "medium", "mcq",
     ("What is 50% of 80?", "80 का 50% कितना है?", "८० च्या ५०% किती?"),
     (["40", "50", "30", "20"], ["40", "50", "30", "20"], ["४०", "५०", "३०", "२०"]),
     0,
     ("50% means half — half of 80 is 40.", "50% = आधा — 80 का आधा 40।", "५०% म्हणजे अर्धा — ८० चा अर्धा ४०.")),
    ("Mathematics", "percentage", "hard", "mcq",
     ("A ₹400 shirt has 25% off. What is the final price?", "₹400 की शर्ट पर 25% छूट। अंतिम कीमत?", "₹४०० च्या शर्टला २५% सवलत. अंतिम किंमत?"),
     (["₹300", "₹375", "₹320", "₹350"], ["₹300", "₹375", "₹320", "₹350"], ["₹३००", "₹३७५", "₹३२०", "₹३५०"]),
     0,
     ("25% of 400 = 100; 400 − 100 = ₹300.", "400 का 25% = 100; 400 − 100 = ₹300।", "४०० च्या २५% = १००; ४०० − १०० = ₹३००.")),
    ("Mathematics", "ratio", "medium", "mcq",
     ("₹10 is divided 2:3. What is the larger share?", "₹10 को 2:3 में बाँटा। बड़ा हिस्सा?", "₹१० चे २:३ ने वाटप. मोठा वाटा?"),
     (["₹6", "₹4", "₹5", "₹3"], ["₹6", "₹4", "₹5", "₹3"], ["₹६", "₹४", "₹५", "₹३"]),
     0,
     ("2+3 = 5 parts; each part ₹2; larger = 3 × ₹2 = ₹6.", "2+3 = 5 भाग; हर भाग ₹2; बड़ा = 3 × ₹2 = ₹6।", "२+३ = ५ भाग; प्रत्येक भाग ₹२; मोठा = ३ × ₹२ = ₹६.")),
    ("Mathematics", "quadratic", "hard", "mcq",
     ("The roots of x² − 9 = 0 are:", "x² − 9 = 0 के मूल हैं:", "x² − 9 = 0 ची मुळे आहेत:"),
     (["3 and −3", "9", "3 only", "0"], ["3 and −3", "9", "3 only", "0"], ["३ आणि −३", "९", "फक्त ३", "०"]),
     0,
     ("x² = 9 → x = +3 or x = −3.", "x² = 9 → x = +3 या −3।", "x² = ९ → x = +३ किंवा −३.")),
    ("Mathematics", "algebra", "medium", "fill",
     ("If x = 4, then 2x + 1 = ____", "यदि x = 4, तो 2x + 1 = ____", "जर x = ४, तर 2x + 1 = ____"),
     ([], [], []),
     "9",
     ("2×4 + 1 = 8 + 1 = 9.", "2×4 + 1 = 8 + 1 = 9।", "२×४ + १ = ८ + १ = ९.")),
    ("Mathematics", "statistics", "medium", "mcq",
     ("What is the mean (average) of 2, 4, 6, 8?", "2, 4, 6, 8 का माध्य (औसत) क्या है?", "२, ४, ६, ८ चा मध्यमान (सरासरी) किती?"),
     (["5", "6", "4", "20"], ["5", "6", "4", "20"], ["५", "६", "४", "२०"]),
     0,
     ("Sum = 20, count = 4 → 20 ÷ 4 = 5.", "योग = 20, संख्या = 4 → 20 ÷ 4 = 5।", "बेरीज = २०, संख्या = ४ → २० ÷ ४ = ५.")),
    # ---- Science: middle (Class 6-8) ----
    ("Science", "cell_biology", "easy", "mcq",
     ("Which organelle is the control center of the cell?", "कोशिका का नियंत्रण केंद्र कौन है?", "पेशीचे नियंत्रण केंद्र कोणते?"),
     (["Nucleus", "Vacuole", "Cell membrane"], ["न्यूक्लियस", "रिक्तिका", "कोशिका झिल्ली"], ["केंद्रक", "रिक्तिका", "पेशीपटल"]),
     0,
     ("The nucleus controls all cell activities.", "न्यूक्लियस कोशिका की सभी क्रियाएँ नियंत्रित करता है।", "केंद्रक सर्व पेशी क्रिया नियंत्रित करते.")),
    ("Science", "cell_biology", "easy", "truefalse",
     ("Plant cells have a cell wall.", "पादप कोशिका में कोशिका भित्ति होती है।", "वनस्पती पेशीला पेशीभित्ती असते."),
     (["True", "False"], ["सही", "गलत"], ["बरोबर", "चूक"]),
     0,
     ("Only plant cells (not animal cells) have a cell wall.", "केवल पादप कोशिका में कोशिका भित्ति होती है, जंतु में नहीं।", "फक्त वनस्पती पेशीला पेशीभित्ती असते, प्राणी पेशीला नाही.")),
    ("Science", "force", "easy", "truefalse",
     ("Force can change the shape of an object.", "बल किसी वस्तु का आकार बदल सकता है।", "बल वस्तूचा आकार बदलू शकतो."),
     (["True", "False"], ["सही", "गलत"], ["बरोबर", "चूक"]),
     0,
     ("Pressing clay changes its shape — force can deform objects.", "मिट्टी दबाने से आकार बदलता है — बल वस्तुएँ विकृत कर सकता है।", "चिकणमाती दाबल्यास आकार बदलतो — बल वस्तू विकृत करू शकतो.")),
    ("Science", "force", "medium", "mcq",
     ("What is the SI unit of force?", "बल की SI इकाई क्या है?", "बलाचे SI एकक काय?"),
     (["Newton", "Kilogram", "Metre", "Joule"], ["न्यूटन", "किलोग्राम", "मीटर", "जूल"], ["न्यूटन", "किलोग्रॅम", "मीटर", "ज्यूल"]),
     0,
     ("Force is measured in newtons (N).", "बल न्यूटन (N) में मापा जाता है।", "बल न्यूटन (N) मध्ये मोजला जातो.")),
    ("Science", "photosynthesis", "easy", "mcq",
     ("Plants make food using ___.", "पौधे ___ का उपयोग करके भोजन बनाते हैं।", "वनस्पती ___ वापरून अन्न बनवतात."),
     (["Sunlight", "Moonlight", "Tube light"], ["धूप", "चाँदनी", "ट्यूब लाइट"], ["सूर्यप्रकाश", "चंद्रप्रकाश", "ट्यूब लाइट"]),
     0,
     ("Photosynthesis uses sunlight, water and CO₂.", "प्रकाश संश्लेषण में धूप, पानी और CO₂ लगता है।", "प्रकाशसंश्लेषणासाठी सूर्यप्रकाश, पाणी आणि CO₂ लागते.")),
    ("Science", "photosynthesis", "medium", "mcq",
     ("Which gas do plants take in during photosynthesis?", "प्रकाश संश्लेषण के समय पौधे कौन सी गैस लेते हैं?", "प्रकाशसंश्लेषणाच्या वेळी वनस्पती कोणता वायू घेतात?"),
     (["Carbon dioxide", "Oxygen", "Nitrogen", "Hydrogen"], ["कार्बन डाइऑक्साइड", "ऑक्सीजन", "नाइट्रोजन", "हाइड्रोजन"], ["कार्बन डायऑक्साइड", "ऑक्सिजन", "नायट्रोजन", "हायड्रोजन"]),
     0,
     ("CO₂ + water + light → food + oxygen.",
      "CO₂ + पानी + प्रकाश → भोजन + ऑक्सीजन।",
      "CO₂ + पाणी + प्रकाश → अन्न + ऑक्सिजन.")),
    ("Science", "human_body", "easy", "mcq",
     ("Which organ pumps blood in our body?", "हमारे शरीर में रक्त कौन पंप करता है?", "शरीरात रक्त कोण पंप करते?"),
     (["Heart", "Lungs", "Liver", "Brain"], ["हृदय", "फेफड़े", "यकृत", "मस्तिष्क"], ["हृदय", "फुफ्फुसे", "यकृत", "मेंदू"]),
     0,
     ("The heart pumps blood to the whole body.", "हृदय पूरे शरीर में रक्त पंप करता है।", "हृदय संपूर्ण शरीरात रक्त पंप करते.")),
    ("Science", "human_body", "medium", "mcq",
     ("How many bones are in an adult human body?", "वयस्क मनुष्य के शरीर में कितनी हड्डियाँ होती हैं?", "प्रौढ माणसाच्या शरीरात किती हाडे असतात?"),
     (["206", "306", "106", "256"], ["206", "306", "106", "256"], ["२०६", "३०६", "१०६", "२५६"]),
     0,
     ("Adults have 206 bones; babies are born with about 300.", "वयस्कों में 206 हड्डियाँ; शिशु ~300 के साथ जन्मते हैं।", "प्रौढांमध्ये २०६ हाडे; बाळांमध्ये सुमारे ३००.")),
    ("Science", "states_of_matter", "easy", "mcq",
     ("Water turning into ice is called:", "पानी का बर्फ बनना कहलाता है:", "पाणी बर्फ होणे म्हणजे:"),
     (["Freezing", "Melting", "Boiling", "Evaporation"], ["जमना", "पिघलना", "उबलना", "वाष्पीकरण"], ["गोठणे", "वितळणे", "उकळणे", "बाष्पीभवन"]),
     0,
     ("Liquid → solid = freezing.", "द्रव → ठोस = जमना (freezing)।", "द्रव → घन = गोठणे.")),
    ("Science", "solar_system", "easy", "mcq",
     ("Which planet is closest to the Sun?", "सूर्य के सबसे नज़दीक कौन सा ग्रह है?", "सूर्याच्या सर्वात जवळ कोणता ग्रह आहे?"),
     (["Mercury", "Venus", "Earth", "Mars"], ["बुध", "शुक्र", "पृथ्वी", "मंगल"], ["बुध", "शुक्र", "पृथ्वी", "मंगळ"]),
     0,
     ("Mercury is the first planet from the Sun.", "बुध सूर्य से पहला ग्रह है।", "बुध सूर्यापासून पहिला ग्रह आहे.")),
    ("Science", "solar_system", "easy", "truefalse",
     ("The Earth revolves around the Sun.", "पृथ्वी सूर्य की परिक्रमा करती है।", "पृथ्वी सूर्याभोवती प्रदक्षिणा घालते."),
     (["True", "False"], ["सही", "गलत"], ["बरोबर", "चूक"]),
     0,
     ("One revolution takes about 365¼ days = 1 year.", "एक परिक्रमा ≈ 365¼ दिन = 1 वर्ष।", "एक प्रदक्षिणा ≈ ३६५¼ दिवस = १ वर्ष.")),
    # ---- Science: secondary (Class 9-10) ----
    ("Science", "chemical_reactions", "medium", "mcq",
     ("Balance: __H₂ + O₂ → 2H₂O. What coefficient goes in the blank?", "संतुलित करें: __H₂ + O₂ → 2H₂O। रिक्त स्थान में क्या आएगा?", "संतुलित करा: __H₂ + O₂ → 2H₂O. रिक्तीत काय येईल?"),
     (["1", "2", "3"], ["1", "2", "3"], ["1", "2", "3"]),
     1,
     ("4H atoms on the right need 4H on the left: 2H₂.", "दाईं ओर 4H के लिए बाईं ओर 2H₂ चाहिए।", "उजवीकडे 4H साठी डावीकडे 2H₂ लागते.")),
    ("Science", "chemical_reactions", "hard", "mcq",
     ("AB → A + B is which type of reaction?", "AB → A + B किस प्रकार की अभिक्रिया है?", "AB → A + B कोणत्या प्रकारची अभिक्रिया आहे?"),
     (["Decomposition", "Combination", "Displacement", "Neutralisation"],
      ["अपघटन", "संयोग", "विस्थापन", "उदासीनीकरण"], ["विघटन", "एकीकरण", "विस्थापन", "तटस्थीकरण"]),
     0,
     ("One substance breaks into two — decomposition.", "एक पदार्थ दो में टूटता है — अपघटन।", "एक पदार्थ दोमध्ये तुटतो — विघटन.")),
    ("Science", "acids_bases", "medium", "mcq",
     ("What is the pH of a neutral solution?", "उदासीन विलयन का pH क्या है?", "तटस्थ द्रावणाचा pH किती?"),
     (["7", "0", "14", "2"], ["7", "0", "14", "2"], ["७", "०", "१४", "२"]),
     0,
     ("Pure water has pH 7 — neutral.", "शुद्ध पानी का pH 7 — उदासीन।", "शुद्ध पाण्याचा pH ७ — तटस्थ.")),
    ("Science", "acids_bases", "easy", "mcq",
     ("Blue litmus turns ___ in an acid.", "अम्ल में नीला लिटमस ___ हो जाता है।", "आम्लात निळा लिटमस ___ होतो."),
     (["Red", "Green", "White", "No change"], ["लाल", "हरा", "सफ़ेद", "कोई बदल नहीं"], ["लाल", "हिरवा", "पांढरा", "बदल नाही"]),
     0,
     ("Acids turn blue litmus red.", "अम्ल नीले लिटमस को लाल कर देते हैं।", "आम्ले निळा लिटमस लाल करतात.")),
    ("Science", "electricity", "medium", "mcq",
     ("What is the SI unit of electric current?", "विद्युत धारा की SI इकाई क्या है?", "विद्युत प्रवाहाचे SI एकक काय?"),
     (["Ampere", "Volt", "Ohm", "Watt"], ["एम्पियर", "वोल्ट", "ओम", "वाट"], ["अँपिअर", "व्होल्ट", "ओहम", "वॅट"]),
     0,
     ("Current is measured in amperes (A).", "धारा एम्पियर (A) में मापी जाती है।", "प्रवाह अँपिअर (A) मध्ये मोजला जातो.")),
    ("Science", "electricity", "hard", "mcq",
     ("Two 4Ω resistors are connected in parallel. Total resistance?", "दो 4Ω प्रतिरोध समांतर में जुड़े हैं। कुल प्रतिरोध?", "दोन ४Ω रोध समांतरमध्ये जोडले आहेत. एकूण रोध?"),
     (["2Ω", "8Ω", "4Ω", "0.5Ω"], ["2Ω", "8Ω", "4Ω", "0.5Ω"], ["२Ω", "८Ω", "४Ω", "०.५Ω"]),
     0,
     ("Parallel: 1/R = 1/4 + 1/4 = 1/2 → R = 2Ω.", "समांतर: 1/R = 1/4 + 1/4 = 1/2 → R = 2Ω।", "समांतर: 1/R = १/४ + १/४ = १/२ → R = २Ω.")),
    ("Science", "life_processes", "medium", "mcq",
     ("Which blood cells fight infection?", "संक्रमण से कौन सी रक्त कोशिकाएँ लड़ती हैं?", "संसर्गाशी कोणत्या रक्तपेशी लढतात?"),
     (["White blood cells", "Red blood cells", "Platelets", "Plasma"],
      ["श्वेत रक्त कोशिकाएँ", "लाल रक्त कोशिकाएँ", "बिंबाणु", "प्लाज़्मा"], ["पांढऱ्या रक्तपेशी", "लाल रक्तपेशी", "रक्तकणिका", "रक्तद्रव"]),
     0,
     ("WBCs are the soldiers of the body.", "श्वेत रक्त कोशिकाएँ शरीर के सैनिक हैं।", "पांढऱ्या रक्तपेशी शरीराचे सैनिक आहेत.")),
    ("Science", "optics", "medium", "mcq",
     ("Which mirror converges (focuses) light?", "कौन सा दर्पण प्रकाश को अभिसरित (फोकस) करता है?", "कोणता आरसा प्रकाश एकवटित (फोकस) करतो?"),
     (["Concave", "Convex", "Plane", "Cylindrical"], ["अवतल", "उत्तल", "समतल", "बेलनाकार"], ["अंतर्गोल", "बहिर्गोल", "सपाट", "दंडगोलाकार"]),
     0,
     ("Concave mirrors bring parallel rays to a focus.", "अवतल दर्पण समांतर किरणों को फोकस करते हैं।", "अंतर्गोल आरसा समांतर किरणे एका बिंदूवर आणतो.")),
    # ---- Physics (HSC) ----
    ("Physics", "electrostatics", "hard", "mcq",
     ("If the distance between two charges doubles, the force becomes:", "यदि दो आवेशों के बीच दूरी दोगुनी हो जाए, तो बल हो जाता है:", "दोन आवेशांमधील अंतर दुप्पट झाल्यास बल असे होते:"),
     (["One-fourth", "Half", "Double", "Four times"], ["एक-चौथाई", "आधा", "दोगुना", "चार गुना"], ["एक-चतुर्थांश", "अर्धा", "दुप्पट", "चारपट"]),
     0,
     ("F ∝ 1/r²: r→2r gives F→F/4.", "F ∝ 1/r²: r→2r पर F→F/4।", "F ∝ १/r²: r→2r मुळे F→F/४.")),
    ("Physics", "electrostatics", "medium", "mcq",
     ("What is the SI unit of electric charge?", "विद्युत आवेश की SI इकाई क्या है?", "विद्युत आवेशाचे SI एकक काय?"),
     (["Coulomb", "Ampere", "Volt", "Farad"], ["कूलॉम", "एम्पियर", "वोल्ट", "फैराड"], ["कूलॉम", "अँपिअर", "व्होल्ट", "फॅरड"]),
     0,
     ("Charge is measured in coulombs (C).", "आवेश कूलॉम (C) में मापा जाता है।", "आवेश कूलॉम (C) मध्ये मोजला जातो.")),
    ("Physics", "motion", "medium", "mcq",
     ("Newton's first law is also called the law of ___?", "न्यूटन का पहला नियम ___ का नियम भी कहलाता है?", "न्यूटनचा पहिला नियम ___ चा नियम म्हणूनही ओळखला जातो?"),
     (["Inertia", "Momentum", "Gravity", "Energy"], ["जड़त्व", "संवेग", "गुरुत्व", "ऊर्जा"], ["जडत्व", "संवेग", "गुरुत्व", "ऊर्जा"]),
     0,
     ("Objects resist changes in motion — that's inertia.", "वस्तुएँ गति में बदल का विरोध करती हैं — यही जड़त्व है।", "वस्तू गतीतील बदलास प्रतिकार करतात — तेच जडत्व.")),
    ("Physics", "motion", "medium", "fill",
     ("Acceleration = change in ____ ÷ time", "त्वरण = ____ में परिवर्तन ÷ समय", "त्वरण = ____ मधील बदल ÷ वेळ"),
     ([], [], []),
     "velocity",
     ("a = Δv/Δt — velocity change per unit time.", "a = Δv/Δt — प्रति इकाई समय वेग परिवर्तन।", "a = Δv/Δt — एकक वेळेतील वेग बदल.")),
    ("Physics", "optics_physics", "hard", "mcq",
     ("Speed of light in vacuum ≈ ?", "निर्वात में प्रकाश की गति ≈ ?", "निर्वातात प्रकाशाचा वेग ≈ ?"),
     (["3×10⁸ m/s", "3×10⁶ m/s", "3×10¹⁰ m/s", "3×10⁴ m/s"],
      ["3×10⁸ मी/से", "3×10⁶ मी/से", "3×10¹⁰ मी/से", "3×10⁴ मी/से"], ["३×१०⁸ मी/से", "३×१०⁶ मी/से", "३×१०¹⁰ मी/से", "३×१०⁴ मी/से"]),
     0,
     ("c ≈ 299,792,458 m/s ≈ 3×10⁸ m/s.", "c ≈ 299,792,458 मी/से ≈ 3×10⁸।", "c ≈ २९,९७,९२,४५८ मी/से ≈ ३×१०⁸.")),
    # ---- Chemistry (HSC) ----
    ("Chemistry", "periodic_table", "medium", "mcq",
     ("The lightest element is:", "सबसे हल्का तत्व है:", "सर्वात हलके मूलद्रव्य:"),
     (["Hydrogen", "Helium", "Oxygen", "Carbon"], ["हाइड्रोजन", "हीलियम", "ऑक्सीजन", "कार्बन"], ["हायड्रोजन", "हिलियम", "ऑक्सिजन", "कार्बन"]),
     0,
     ("Hydrogen is #1 on the periodic table.", "हाइड्रोजन आवर्त सारणी में #1 है।", "हायड्रोजन आवर्त सारणीत पहिला आहे.")),
    ("Chemistry", "periodic_table", "hard", "mcq",
     ("Which element has the symbol 'Na'?", "'Na' प्रतीक किस तत्व का है?", "'Na' चिन्ह कोणत्या मूलद्रव्याचे आहे?"),
     (["Sodium", "Nitrogen", "Neon", "Nickel"], ["सोडियम", "नाइट्रोजन", "निऑन", "निकल"], ["सोडियम", "नायट्रोजन", "निऑन", "निकेल"]),
     0,
     ("Na comes from 'Natrium' — sodium.", "Na 'Natrium' से — सोडियम।", "Na 'Natrium' मधून — सोडियम.")),
    ("Chemistry", "mole_concept", "hard", "mcq",
     ("Avogadro's number is approximately:", "एवोगाद्रो संख्या लगभग है:", "अवोगाद्रो संख्या सुमारे:"),
     (["6.022×10²³", "6.022×10²²", "3.14×10²³", "9.8×10²³"],
      ["6.022×10²³", "6.022×10²²", "3.14×10²³", "9.8×10²³"], ["६.०२२×१०²³", "६.०२२×१०²²", "३.१४×१०²³", "९.८×१०²³"]),
     0,
     ("1 mole = 6.022×10²³ particles.", "1 मोल = 6.022×10²³ कण।", "१ मोल = ६.०२२×१०²³ कण.")),
    # ---- Biology (HSC) ----
    ("Biology", "genetics", "medium", "mcq",
     ("DNA carries ___", "DNA ___ ले जाता है", "DNA ___ वाहून नेते"),
     (["Genetic information", "Oxygen", "Food", "Water"],
      ["आनुवंशिक सूचना", "ऑक्सीजन", "भोजन", "पानी"], ["अनुवंशिक माहिती", "ऑक्सिजन", "अन्न", "पाणी"]),
     0,
     ("DNA stores the hereditary information of life.", "DNA जीवन की आनुवंशिक जानकारी संग्रहित करता है।", "DNA जीवनाची अनुवंशिक माहिती साठवते.")),
    ("Biology", "genetics", "hard", "mcq",
     ("Who proposed the laws of inheritance?", "आनुवंशिकता के नियम किसने दिए?", "आनुवंशिकतेचे नियम कोणी मांडले?"),
     (["Mendel", "Darwin", "Newton", "Einstein"], ["मेंडल", "डार्विन", "न्यूटन", "आइंस्टीन"], ["मेंडेल", "डार्विन", "न्यूटन", "आइन्स्टाइन"]),
     0,
     ("Gregor Mendel, from pea-plant experiments.", "ग्रेगर मेंडल, मटर के पौधों के प्रयोगों से।", "ग्रेगर मेंडेल, मटकी-वनस्पती प्रयोगांतून.")),
    ("Biology", "cells_hsc", "medium", "mcq",
     ("Which organelle is called the 'powerhouse of the cell'?", "किसे 'कोशिका का पावरहाउस' कहते हैं?", "कोणाला 'पेशीचे पॉवरहाऊस' म्हणतात?"),
     (["Mitochondria", "Nucleus", "Ribosome", "Vacuole"],
      ["माइटोकॉन्ड्रिया", "न्यूक्लियस", "राइबोसोम", "रिक्तिका"], ["मायटोकॉन्ड्रिया", "केंद्रक", "रायबोसोम", "रिक्तिका"]),
     0,
     ("Mitochondria produce ATP — the cell's energy.", "माइटोकॉन्ड्रिया ATP बनाते हैं — कोशिका की ऊर्जा।", "मायटोकॉन्ड्रिया ATP तयार करतात — पेशीची ऊर्जा.")),
    # ---- Computer Science (HSC) ----
    ("Computer Science", "programming", "easy", "mcq",
     ("What does CPU stand for?", "CPU का पूरा नाम क्या है?", "CPU चे संपूर्ण नाव काय?"),
     (["Central Processing Unit", "Computer Personal Unit", "Central Print Unit", "Control Program Unit"],
      ["सेंट्रल प्रोसेसिंग यूनिट", "कंप्यूटर पर्सनल यूनिट", "सेंट्रल प्रिंट यूनिट", "कंट्रोल प्रोग्राम यूनिट"],
      ["सेंट्रल प्रोसेसिंग युनिट", "कॉम्प्युटर पर्सनल युनिट", "सेंट्रल प्रिंट युनिट", "कंट्रोल प्रोग्राम युनिट"]),
     0,
     ("CPU = Central Processing Unit — the brain of the computer.", "CPU = सेंट्रल प्रोसेसिंग यूनिट — कंप्यूटर का दिमाग।", "CPU = सेंट्रल प्रोसेसिंग युनिट — संगणकाचे मेंदू.")),
    ("Computer Science", "programming", "medium", "mcq",
     ("What is the binary of decimal 5?", "दशमलव 5 का द्विआधारी (binary) क्या है?", "दशांश ५ चे द्विअंकी (binary) काय?"),
     (["101", "110", "100", "111"], ["101", "110", "100", "111"], ["१०१", "११०", "१००", "१११"]),
     0,
     ("5 = 4 + 1 = 1×4 + 0×2 + 1×1 = 101.", "5 = 4 + 1 = 101 (बाइनरी)।", "५ = ४ + १ = १०१ (बायनरी).")),
    ("Computer Science", "programming", "easy", "truefalse",
     ("RAM is a permanent memory.", "RAM एक स्थायी मेमोरी है।", "RAM कायमस्वरूपी मेमरी आहे."),
     (["True", "False"], ["सही", "गलत"], ["बरोबर", "चूक"]),
     1,
     ("RAM is temporary — data is lost when power goes off.", "RAM अस्थायी है — बिजली जाने पर डेटा मिट जाता है।", "RAM तात्पुरती आहे — वीज गेल्यास डेटा नाहीसा होतो.")),
    ("Computer Science", "internet", "medium", "mcq",
     ("WWW stands for:", "WWW का पूरा नाम:", "WWW चे संपूर्ण नाव:"),
     (["World Wide Web", "World Web Wide", "Wide World Web", "Web World Wide"],
      ["वर्ल्ड वाइड वेब", "वर्ल्ड वेब वाइड", "वाइड वर्ल्ड वेब", "वेब वर्ल्ड वाइड"],
      ["वर्ल्ड वाइड वेब", "वर्ल्ड वेब वाइड", "वायड वर्ल्ड वेब", "वेब वर्ल्ड वाइड"]),
     0,
     ("WWW = World Wide Web, invented by Tim Berners-Lee.", "WWW = वर्ल्ड वाइड वेब, टिम बर्नर्स-ली द्वारा।", "WWW = वर्ल्ड वाइड वेब, टिम बर्नर्स-ली यांनी बनवले.")),
    # ---- Marathi ----
    ("Marathi", "reading", "easy", "mcq",
     ("'मी शाळेत जातो.' — या वाक्याचा अर्थ काय?", "'मी शाळेत जातो।' — इस वाक्य का अर्थ?", "'मी शाळेत जातो.' — या वाक्याचा अर्थ काय?"),
     (["I go to school", "She reads a book", "We play"], ["मैं स्कूल जाता हूँ", "वह पुस्तक पढ़ती है", "हम खेलते हैं"], ["मी शाळेत जातो", "ती पुस्तक वाचते", "आम्ही खेळतो"]),
     0,
     ("मी = I, शाळेत = to school, जातो = go.", "मी = मैं, शाळेत = स्कूल, जातो = जाता हूँ।", "मी = I, शाळेत = school, जातो = go.")),
    ("Marathi", "vocabulary_mr", "easy", "mcq",
     ("'पुस्तक' म्हणजे काय?", "'पुस्तक' का अर्थ क्या है?", "'पुस्तक' म्हणजे काय?"),
     (["Book", "Pen", "Bag", "School"], ["पुस्तक (Book)", "पेन (Pen)", "बैग (Bag)", "स्कूल (School)"], ["पुस्तक", "पेन", "बॅग", "शाळा"]),
     0,
     ("पुस्तक = book — we read it daily.", "पुस्तक = book — हम इसे रोज़ पढ़ते हैं।", "पुस्तक म्हणजे book — ते आपण रोज वाचतो.")),
    ("Marathi", "grammar_mr", "medium", "mcq",
     ("मराठी व्याकरणात 'मी' कोणत्या पुरुषाचे सर्वनाम आहे?", "मराठी व्याकरण में 'मी' किस पुरुष का सर्वनाम है?", "मराठी व्याकरणात 'मी' कोणत्या पुरुषाचे सर्वनाम आहे?"),
     (["प्रथम पुरुष (First person)", "द्वितीय पुरुष (Second person)", "तृतीय पुरुष (Third person)", "कोणतेही नाही (None)"],
      ["प्रथम पुरुष", "द्वितीय पुरुष", "तृतीय पुरुष", "कोई नहीं"], ["प्रथम पुरुष", "द्वितीय पुरुष", "तृतीय पुरुष", "काही नाही"]),
     0,
     ("'मी' = प्रथम पुरुष सर्वनाम (first person).", "'मी' प्रथम पुरुष सर्वनाम है।", "'मी' = प्रथम पुरुष सर्वनाम.")),
    # ---- Hindi ----
    ("Hindi", "vocabulary_hi", "easy", "mcq",
     ("'विद्यालय' का अर्थ क्या है?", "'विद्यालय' म्हणजे काय?", "'विद्यालय' का अर्थ काय?"),
     (["School", "Market", "River", "Village"], ["स्कूल", "बाज़ार", "नदी", "गाँव"], ["शाळा", "बाजार", "नदी", "गाव"]),
     0,
     ("विद्यालय = school (विद्या + आलय).", "विद्यालय = स्कूल (विद्या + आलय)।", "विद्यालय म्हणजे शाळा (विद्या + आलय).")),
    ("Hindi", "grammar_hi", "medium", "mcq",
     ("'दिन' का विलोम (विरुद्धार्थी) शब्द क्या है?", "'दिन' चा विरुद्धार्थी शब्द काय?", "'दिन' का विलोम (विरुद्धार्थी) शब्द क्या है?"),
     (["रात", "सुबह", "शाम", "प्रकाश"], ["रात", "सकाळ", "संध्याकाळ", "प्रकाश"], ["रात्र", "सकाळ", "संध्याकाळ", "प्रकाश"]),
     0,
     ("दिन × रात — opposite words.", "दिन × रात — विलोम शब्द।", "दिवस × रात्र — विरुद्धार्थी शब्द.")),
    # ---- English ----
    ("English", "grammar_en", "easy", "mcq",
     ("What is the plural of 'book'?", "'book' का बहुवचन क्या है?", "'book' चे अनेकवचन काय?"),
     (["Books", "Bookes", "Book's", "Book"], ["Books", "Bookes", "Book's", "Book"], ["Books", "Bookes", "Book's", "Book"]),
     0,
     ("Add -s: one book → many books.", "-s जोड़ो: one book → many books।", "-s जोडा: one book → many books.")),
    ("English", "grammar_en", "medium", "mcq",
     ("Choose the correct sentence:", "सही वाक्य चुनें:", "योग्य वाक्य निवडा:"),
     (["She goes to school.", "She go to school.", "She going school.", "She gone school."],
      ["She goes to school.", "She go to school.", "She going school.", "She gone school."],
      ["She goes to school.", "She go to school.", "She going school.", "She gone school."]),
     0,
     ("Third person singular (she) takes 'goes'.", "तीसरे पुरुष एकवचन (she) के साथ 'goes' आता है।", "तृतीय पुरुष एकवचन (she) साठी 'goes' येते.")),
    ("English", "vocabulary_en", "easy", "mcq",
     ("What is the opposite of 'big'?", "'big' का विलोम क्या है?", "'big' चा विरुद्धार्थी काय?"),
     (["Small", "Tall", "Large", "Huge"], ["छोटा", "लंबा", "बड़ा", "विशाल"], ["लहान", "उंच", "मोठे", "प्रचंड"]),
     0,
     ("big × small are opposites.", "big × small विलोम हैं।", "big × small विरुद्धार्थी आहेत.")),
    # ---- Social Science ----
    ("History", "freedom_struggle", "medium", "mcq",
     ("Who is called the 'Father of the Nation' in India?", "भारत में 'राष्ट्रपिता' किसे कहा जाता है?", "भारतात 'राष्ट्रपिता' कोणाला म्हणतात?"),
     (["Mahatma Gandhi", "Jawaharlal Nehru", "Bhagat Singh", "Dr. Ambedkar"],
      ["महात्मा गांधी", "जवाहरलाल नेहरू", "भगत सिंह", "डॉ. आंबेडकर"], ["महात्मा गांधी", "जवाहरलाल नेहरू", "भगत सिंग", "डॉ. आंबेडकर"]),
     0,
     ("Gandhiji is called 'Rashtrapita' — Father of the Nation.", "गांधीजी को 'राष्ट्रपिता' कहा जाता है।", "गांधीजींना 'राष्ट्रपिता' म्हणतात.")),
    ("Geography", "continents", "easy", "mcq",
     ("Which is the largest continent?", "सबसे बड़ा महाद्वीप कौन सा है?", "सर्वात मोठा खंड कोणता?"),
     (["Asia", "Africa", "Europe", "Australia"], ["एशिया", "अफ्रीका", "यूरोप", "ऑस्ट्रेलिया"], ["आशिया", "आफ्रिका", "युरोप", "ऑस्ट्रेलिया"]),
     0,
     ("Asia is the largest continent — India is part of it.", "एशिया सबसे बड़ा महाद्वीप है — भारत उसी का हिस्सा है।", "आशिया सर्वात मोठा खंड आहे — भारत त्याचा भाग आहे.")),
    ("Geography", "rivers", "medium", "mcq",
     ("Which is the longest river in India?", "भारत की सबसे लंबी नदी कौन सी है?", "भारतातील सर्वात लांब नदी कोणती?"),
     (["Ganga", "Yamuna", "Godavari", "Narmada"], ["गंगा", "यमुना", "गोदावरी", "नर्मदा"], ["गंगा", "यमुना", "गोदावरी", "नर्मदा"]),
     0,
     ("The Ganga is about 2,525 km long.", "गंगा लगभग 2,525 किमी लंबी है।", "गंगा सुमारे २,५२५ किमी लांब आहे.")),
    ("Social Science", "civics", "easy", "mcq",
     ("What is the national animal of India?", "भारत का राष्ट्रीय पशु क्या है?", "भारताचा राष्ट्रीय प्राणी कोणता?"),
     (["Tiger", "Lion", "Elephant", "Peacock"], ["बाघ", "सिंह", "हाथी", "मोर"], ["वाघ", "सिंह", "हत्ती", "मोर"]),
     0,
     ("The Royal Bengal Tiger is India's national animal.", "रॉयल बंगाल टाइगर भारत का राष्ट्रीय पशु है।", "रॉयल बंगाल वाघ हा भारताचा राष्ट्रीय प्राणी आहे.")),
]

TEXTBOOKS = [
    # Board, class, subject, lang, title, official source URL
    ("CBSE", 8, "Science", "en", "Science — Textbook for Class 8 (NCERT)",
     "https://epathshala.nic.in/process.php?id=students&type=eTextbooks&ln=en"),
    ("CBSE", 8, "Mathematics", "en", "Mathematics — Textbook for Class 8 (NCERT)",
     "https://epathshala.nic.in/process.php?id=students&type=eTextbooks&ln=en"),
    ("CBSE", 10, "Science", "hi", "विज्ञान — कक्षा 10 (NCERT)",
     "https://epathshala.nic.in/process.php?id=students&type=eTextbooks&ln=hi"),
    ("CBSE", 10, "Mathematics", "hi", "गणित — कक्षा 10 (NCERT)",
     "https://epathshala.nic.in/process.php?id=students&type=eTextbooks&ln=hi"),
    ("CBSE", 7, "Science", "en", "Science — Textbook for Class 7 (NCERT)",
     "https://epathshala.nic.in/process.php?id=students&type=eTextbooks&ln=en"),
    ("CBSE", 12, "Physics", "en", "Physics Part I — Textbook for Class 12 (NCERT)",
     "https://epathshala.nic.in/process.php?id=students&type=eTextbooks&ln=en"),
    ("Maharashtra SSC", 8, "Science", "mr", "सामान्य विज्ञान — इयत्ता ८ (बालभारती)",
     "https://books.ebalbharati.in"),
    ("Maharashtra SSC", 8, "Mathematics", "mr", "गणित — इयत्ता ८ (बालभारती)",
     "https://books.ebalbharati.in"),
    ("Maharashtra SSC", 5, "Marathi", "mr", "मराठी — इयत्ता ५ (बालभारती)",
     "https://books.ebalbharati.in"),
    ("Maharashtra SSC", 6, "Marathi", "mr", "मराठी — इयत्ता ६ (बालभारती)",
     "https://books.ebalbharati.in"),
    ("Maharashtra SSC", 7, "Hindi", "hi", "हिंदी — इयत्ता ७ (बालभारती)",
     "https://books.ebalbharati.in"),
    ("Maharashtra SSC", 10, "Science", "mr", "विज्ञान — इयत्ता १० (बालभारती)",
     "https://books.ebalbharati.in"),
    ("Maharashtra SSC", 10, "Mathematics", "mr", "गणित — इयत्ता १० (बालभारती)",
     "https://books.ebalbharati.in"),
    ("Maharashtra SSC", 1, "Mathematics", "mr", "गणित — इयत्ता १ (बालभारती)",
     "https://books.ebalbharati.in"),
    ("Maharashtra HSC", 12, "Physics", "en", "Physics — Std 12 (Balbharati)",
     "https://books.ebalbharati.in"),
    ("Maharashtra HSC", 12, "Chemistry", "en", "Chemistry — Std 12 (Balbharati)",
     "https://books.ebalbharati.in"),
    ("Maharashtra HSC", 12, "Biology", "en", "Biology — Std 12 (Balbharati)",
     "https://books.ebalbharati.in"),
]


def _subject_for_slug(slug: str) -> str:
    """Map a course slug to the question-bank subject name."""
    if "physics" in slug:
        return "Physics"
    if "science" in slug:
        return "Science"
    if "math" in slug:
        return "Mathematics"
    if "hindi" in slug:
        return "Hindi"
    if "marathi" in slug:
        return "Marathi"
    if "english" in slug:
        return "English"
    return "General"


def seed(session: Session) -> None:
    """Idempotent & additive: only inserts what's missing; safe on existing DBs."""
    if session.exec(select(Board)).first() is None:
        for b in BOARDS:
            session.add(Board(name=b))

    school = session.exec(select(School).where(
        School.name == "Zilla Parishad Prathamik Shala, Rampur")).first()
    if not school:
        school = School(name="Zilla Parishad Prathamik Shala, Rampur", village="Rampur")
        session.add(school)
        session.flush()

    # --- subjects for all classes ---
    if not session.exec(select(Subject)).first():
        for grade in range(1, 13):
            band = (SUBJECTS_PRIMARY if grade <= 5 else
                    SUBJECTS_MIDDLE if grade <= 8 else
                    SUBJECTS_SECONDARY if grade <= 10 else SUBJECTS_HSC)
            for en, hi, mr in band:
                board = "CBSE" if grade in (10, 12) else "Maharashtra SSC"
                session.add(Subject(name_en=en, name_hi=hi, name_mr=mr,
                                    class_grade=grade, board=board))

    # --- users ---
    demo_users = [
        ("admin@gramshiksha.in", "Platform Admin", "platform_admin", "Admin@1234", None, None),
        ("school@gramshiksha.in", "Headmaster Jadhav", "school_admin", "School@1234", 8, "Maharashtra SSC"),
        ("teacher1@gramshiksha.in", "Sunita Devi", "teacher", "Teach@1234", None, None),
        ("teacher2@gramshiksha.in", "Rahul Patil", "teacher", "Teach@1234", None, None),
        ("student1@gramshiksha.in", "Arjun Kumar", "student", "Learn@1234", 8, "Maharashtra SSC"),
        ("student2@gramshiksha.in", "Priya Sharma", "student", "Learn@1234", 10, "CBSE"),
        ("parent1@gramshiksha.in", "Ramesh Kumar", "parent", "Parent@1234", None, None),
    ]
    users = {}
    for email, name, role, pwd, grade, board in demo_users:
        u = session.exec(select(User).where(User.email == email)).first()
        if not u:
            u = User(email=email, name=name, role=role, hashed_password=hash_password(pwd),
                     class_grade=grade, board=board,
                     lang_pref="mr" if email == "student1@gramshiksha.in" else ("hi" if role != "student" else "en"),
                     school_id=school.id if role in ("school_admin", "student") else None)
            session.add(u)
            session.flush()
        users[email] = u

    student1 = users["student1@gramshiksha.in"]
    student2 = users["student2@gramshiksha.in"]
    parent1 = users["parent1@gramshiksha.in"]
    teacher1 = users["teacher1@gramshiksha.in"]
    teacher2 = users["teacher2@gramshiksha.in"]
    _ = users.get("admin@gramshiksha.in"), users.get("school@gramshiksha.in")
    if not student1.parent_of_id:
        student1.parent_of_id = parent1.id  # child carries link to parent
        session.add(student1)

    # --- courses (shells) ---
    courses_by_slug = {}
    for slug, grade, board, subj, lang, titles, diff, dur in COURSES:
        c = session.exec(select(Course).where(Course.slug == slug)).first()
        if not c:
            subject_row = session.exec(select(Subject).where(
                Subject.class_grade == grade, Subject.name_en == subj)).first()
            c = Course(slug=slug, subject_id=subject_row.id if subject_row else 1, board=board,
                       class_grade=grade, lang=lang,
                       title_en=titles[0], title_hi=titles[1], title_mr=titles[2],
                       desc_en=f"Complete {subj} course for Class {grade} ({board}) with lessons, practice and quizzes.",
                       desc_hi=f"कक्षा {grade} ({board}) का पूरा {subj} कोर्स — पाठ, अभ्यास और क्विज़ के साथ।",
                       desc_mr=f"इयत्ता {grade} ({board}) साठी संपूर्ण {subj} कोर्स — धडे, सराव आणि क्विझसह.",
                       teacher_id=teacher1.id if subj in ("Mathematics", "Science", "Physics") else teacher2.id,
                       difficulty=diff, duration_min=dur,
                       students_count=random.choice([40, 55, 78, 120, 210]),
                       rating=round(4.2 + random.random() * 0.7, 1))
            session.add(c)
            session.flush()
        courses_by_slug[slug] = c

    # --- question bank (idempotent per prompt) ---
    for subj, topic, diff, qtype, prompts, options3, correct, expl in QUESTIONS:
        exists = session.exec(select(Question).where(Question.prompt_en == prompts[0])).first()
        if exists:
            continue
        session.add(Question(
            type=qtype, subject_name=subj, topic=topic, difficulty=diff,
            prompt_en=prompts[0], prompt_hi=prompts[1], prompt_mr=prompts[2],
            options_en=json.dumps(options3[0], ensure_ascii=False),
            options_hi=json.dumps(options3[1], ensure_ascii=False),
            options_mr=json.dumps(options3[2], ensure_ascii=False),
            correct=json.dumps(correct) if isinstance(correct, list) else str(correct),
            explanation_en=expl[0], explanation_hi=expl[1], explanation_mr=expl[2],
        ))
    session.flush()
    question_cache: list[Question] = list(session.exec(select(Question)).all())

    # --- chapters + lessons (additive: match by course + chapter/lesson title) ---
    for slug, chapters in COURSE_CONTENT.items():
        c = courses_by_slug[slug]
        subj_name = _subject_for_slug(slug)
        for ch_order, (ch_titles, lessons) in enumerate(chapters, start=1):
            ch = session.exec(select(Chapter).where(
                Chapter.course_id == c.id, Chapter.title_en == ch_titles[0])).first()
            if not ch:
                ch = Chapter(course_id=c.id, order=ch_order,
                             title_en=ch_titles[0], title_hi=ch_titles[1], title_mr=ch_titles[2])
                session.add(ch)
                session.flush()
            for l_order, (l_titles, ltype, mins, body_en, body_hi, body_mr) in enumerate(lessons, start=1):
                lesson = session.exec(select(Lesson).where(
                    Lesson.chapter_id == ch.id, Lesson.title_en == l_titles[0])).first()
                if not lesson:
                    lesson = Lesson(chapter_id=ch.id, order=l_order, type=ltype,
                                    title_en=l_titles[0], title_hi=l_titles[1], title_mr=l_titles[2],
                                    body_en=body_en, body_hi=body_hi, body_mr=body_mr,
                                    duration_min=mins,
                                    video_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ" if ltype == "video" else None,
                                    estimate_mb=round(mins * (0.9 if ltype == "video" else 0.05), 2))
                    session.add(lesson)
                    session.flush()
                # spread subject questions over each chapter's first lesson (up to 5 each)
                if l_order == 1:
                    unattached = [q for q in question_cache
                                  if q.subject_name == subj_name and q.lesson_id is None][:5]
                    for q in unattached:
                        q.lesson_id = lesson.id
                        session.add(q)

    # --- quizzes: one per chapter (idempotent) ---
    for slug, chapters in COURSE_CONTENT.items():
        c = courses_by_slug[slug]
        subj_name = _subject_for_slug(slug)
        for ch_titles, _lessons in chapters:
            ch = session.exec(select(Chapter).where(
                Chapter.course_id == c.id, Chapter.title_en == ch_titles[0])).first()
            if ch and not session.exec(select(Quiz).where(Quiz.chapter_id == ch.id)).first():
                quiz = Quiz(title_en=f"{c.title_en} — {ch_titles[0]} Quiz",
                            title_hi=f"{c.title_hi} — {ch_titles[1]} क्विज़",
                            title_mr=f"{c.title_mr} — {ch_titles[2]} क्विझ",
                            chapter_id=ch.id, time_limit_min=15)
                session.add(quiz)
                session.flush()
                related = [q for q in question_cache if q.subject_name == subj_name][:5]
                for i, q in enumerate(related, start=1):
                    session.add(QuizQuestion(quiz_id=quiz.id, question_id=q.id, order=i))

    # --- textbooks ---
    if not session.exec(select(Textbook)).first():
        for board, grade, subj, lang, title, url in TEXTBOOKS:
            session.add(Textbook(board=board, class_grade=grade, subject_name=subj,
                                 lang=lang, title=title, source_url=url, publisher="Official"))

    # --- enrollments & demo activity (only on first ever seed) ---
    if not session.exec(select(Enrollment)).first():
        session.add(Enrollment(user_id=student1.id, course_id=courses_by_slug["g8-ssc-science-course"].id, progress_pct=12.5))
        session.add(Enrollment(user_id=student1.id, course_id=courses_by_slug["g8-ssc-math-course"].id, progress_pct=0))
        session.add(Enrollment(user_id=student2.id, course_id=courses_by_slug["g10-cbse-science-course"].id, progress_pct=40))
        # weak topic stats for student1: fractions 8/20 = 40%
        session.add(TopicStats(user_id=student1.id, subject_name="Mathematics", topic="fractions",
                               attempted=20, correct=8))
        from datetime import date, timedelta
        for i, (ok, mins) in enumerate([(True, 15), (True, 20), (False, 10), (True, 12)]):
            d = (date.today() - timedelta(days=3 - i)).isoformat()
            session.add(DailyActivity(user_id=student1.id, date=d, minutes=mins,
                                      lessons_completed=1 if ok else 0, quizzes_taken=1 if i == 3 else 0))
        session.add(Doubt(student_id=student1.id, subject_name="Science",
                          chapter_title="Living World",
                          text="What is the difference between plant cell and animal cell?"))
        d2 = Doubt(student_id=student2.id, subject_name="Mathematics",
                   chapter_title="Linear Equations",
                   text="How do we solve equations with variables on both sides?")
        session.add(d2)
        session.flush()
        session.add(DoubtReply(doubt_id=d2.id, teacher_id=teacher1.id,
                               body="Move all variable terms to one side by subtracting. Example: 3x+2=x+10 → 2x=8 → x=4."))
        d2.status = "answered"
        session.add(d2)
        session.add(Notification(user_id=student1.id, type="welcome",
                                 payload=json.dumps({"title": "Welcome to GramShiksha!", "body": "Start with Today's Learning."})))
        session.add(Notification(user_id=student1.id, type="badge", payload=json.dumps({"badge": "first_lesson"})))
        session.add(Material(
            title="Class 8 Science — Chapter 1 Revision Notes",
            description="Short revision notes for Living World chapter",
            type="revision_notes", class_grade=8, board="Maharashtra SSC", subject_name="Science",
            chapter_title="Living World", lang="mr", uploader_id=teacher1.id, uploader_role="teacher",
            visibility="public", status="approved", source_of_content="Created by teacher"))
        session.add(Material(
            title="My handwritten notes — Fractions",
            description="Student-made notes with examples",
            type="notes", class_grade=8, board="Maharashtra SSC", subject_name="Mathematics",
            chapter_title="Rational Numbers", lang="mr", uploader_id=student2.id, uploader_role="student",
            visibility="public", status="pending", source_of_content="Created by student"))

    seed_badges(session)
    session.commit()
