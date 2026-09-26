"""BodyParts3D structures used for the face, grouped by tissue.

BodyParts3D, (c) The Database Center for Life Science (DBCLS), licensed under CC BY-SA 2.1 JP.
Meshes derive from the segmentation of a full-body human dataset and are mapped to the
Foundational Model of Anatomy (FMA) identifiers used as keys here.
"""

SOURCE = ("https://raw.githubusercontent.com/Kevin-Mattheus-Moerman/BodyParts3D/main/"
          "assets/BodyParts3D_data/stl/{fma}.stl")
ATTRIBUTION = ("BodyParts3D, (c) The Database Center for Life Science, licensed under "
               "CC Attribution-Share Alike 2.1 Japan")

# fma id -> (Italian name, tissue)
STRUTTURE = {
    # skin
    "FMA7163": ("Cute", "skin"),
    "FMA71098": ("Sopracciglia", "eyebrow"),
    # skeleton
    "FMA52734": ("Osso frontale", "bone"),
    "FMA53647": ("Osso nasale destro", "bone"), "FMA53648": ("Osso nasale sinistro", "bone"),
    "FMA53649": ("Mascella destra", "bone"), "FMA53650": ("Mascella sinistra", "bone"),
    "FMA52892": ("Osso zigomatico destro", "bone"), "FMA52893": ("Osso zigomatico sinistro", "bone"),
    "FMA52748": ("Mandibola", "bone"),
    "FMA53645": ("Osso lacrimale destro", "bone"), "FMA53646": ("Osso lacrimale sinistro", "bone"),
    "FMA52740": ("Etmoide", "bone"), "FMA52736": ("Sfenoide", "bone"), "FMA9710": ("Vomere", "bone"),
    "FMA53655": ("Osso palatino destro", "bone"), "FMA53656": ("Osso palatino sinistro", "bone"),
    "FMA54737": ("Cornetto inferiore destro", "bone"), "FMA54738": ("Cornetto inferiore sinistro", "bone"),
    "FMA52738": ("Osso temporale destro", "bone"), "FMA52739": ("Osso temporale sinistro", "bone"),
    "FMA52788": ("Osso parietale destro", "bone"), "FMA52789": ("Osso parietale sinistro", "bone"),
    # cartilage and eyes
    "FMA71704": ("Cartilagini nasali", "cartilage"),
    "FMA12513": ("Bulbo oculare", "eye"),
    # muscles of facial expression and mastication
    "FMA46759": ("M. frontale destro", "muscle"), "FMA46760": ("M. frontale sinistro", "muscle"),
    "FMA46796": ("M. corrugatore destro", "muscle"), "FMA46797": ("M. corrugatore sinistro", "muscle"),
    "FMA55610": ("M. procero destro", "muscle"), "FMA55611": ("M. procero sinistro", "muscle"),
    "FMA55606": ("M. nasale destro", "muscle"), "FMA55607": ("M. nasale sinistro", "muscle"),
    "FMA55608": ("M. depressore del setto destro", "muscle"),
    "FMA55609": ("M. depressore del setto sinistro", "muscle"),
    "FMA46782": ("M. orbicolare dell'occhio, parte orbitale dx", "muscle"),
    "FMA46783": ("M. orbicolare dell'occhio, parte orbitale sx", "muscle"),
    "FMA46785": ("M. orbicolare dell'occhio, parte palpebrale dx", "muscle"),
    "FMA46786": ("M. orbicolare dell'occhio, parte palpebrale sx", "muscle"),
    "FMA46803": ("M. elevatore del labbro sup. e dell'ala del naso dx", "muscle"),
    "FMA46804": ("M. elevatore del labbro sup. e dell'ala del naso sx", "muscle"),
    "FMA46806": ("M. elevatore del labbro superiore dx", "muscle"),
    "FMA46807": ("M. elevatore del labbro superiore sx", "muscle"),
    "FMA46812": ("M. grande zigomatico dx", "muscle"), "FMA46813": ("M. grande zigomatico sx", "muscle"),
    "FMA46814": ("M. piccolo zigomatico dx", "muscle"), "FMA46815": ("M. piccolo zigomatico sx", "muscle"),
    "FMA46839": ("M. risorio dx", "muscle"), "FMA46840": ("M. risorio sx", "muscle"),
    "FMA46841": ("M. orbicolare della bocca", "muscle"),
    "FMA46829": ("M. depressore dell'angolo della bocca dx", "muscle"),
    "FMA46830": ("M. depressore dell'angolo della bocca sx", "muscle"),
    "FMA46817": ("M. depressore del labbro inferiore dx", "muscle"),
    "FMA46818": ("M. depressore del labbro inferiore sx", "muscle"),
    "FMA46826": ("M. mentale dx", "muscle"), "FMA46827": ("M. mentale sx", "muscle"),
    "FMA46835": ("M. buccinatore dx", "muscle"), "FMA46836": ("M. buccinatore sx", "muscle"),
    "FMA49001": ("M. massetere, parte superficiale dx", "muscle"),
    "FMA49002": ("M. massetere, parte superficiale sx", "muscle"),
    "FMA49007": ("M. temporale dx", "muscle"), "FMA49008": ("M. temporale sx", "muscle"),
    "FMA45739": ("Platisma dx", "muscle"), "FMA45740": ("Platisma sx", "muscle"),
}

TEETH = ["FMA55680", "FMA55681", "FMA55682", "FMA55683", "FMA55798", "FMA55799", "FMA55688",
         "FMA55689", "FMA55690", "FMA55691", "FMA55697", "FMA55698", "FMA55699", "FMA55700",
         "FMA57140", "FMA57141", "FMA57142", "FMA57143", "FMA55686", "FMA55687", "FMA55692",
         "FMA55693", "FMA55694", "FMA55695", "FMA55703", "FMA55704", "FMA55705", "FMA55706"]
for _t in TEETH:
    STRUTTURE[_t] = ("Dente", "tooth")
