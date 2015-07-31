# Online Corpus Editor
# Language Identification
# Constants


# ===========================
# Table of Valid Pinyin Words
# ===========================
# Valid combinations of initials and finals for pinyin (excluding tone
# marks/number suffixes)
# (http://pinyin.info/rules/initials_finals.html)
def tabulate_pinyin():
    table = {}
    # Initialise
    all_initials = set("bpmfdtnlgkhzcsrjqxwy") | {'zh', 'ch', 'sh'}
    for initial in all_initials:
        table[initial] = []
    # a
    for initial in all_initials - set("rjqx"):
        table[initial].append("a")
    # o
    for initial in set("bpmfw"):
        table[initial].append("o")
    # e
    for initial in all_initials - set("bpfjqxw"):
        table[initial].append("e")
    # ai
    for initial in all_initials - set("frjqxy"):
        table[initial].append("ai")
    # ei
    for initial in all_initials - set("csrjqxy") - {'ch'}:
        table[initial].append("ei")
    # ao
    for initial in all_initials - set("fjqxw"):
        table[initial].append("ao")
    # ou
    for initial in all_initials - set("bjqxw"):
        table[initial].append("ou")
    # an
    # ang
    # u
    for initial in all_initials - set("jqx"):
        table[initial].append("an")
        table[initial].append("ang")
        table[initial].append("u")
    # en
    for initial in all_initials - set("tljqxy"):
        table[initial].append("en")
    # eng
    for initial in all_initials - set("jqxy"):
        table[initial].append("eng")
    # ong
    for initial in all_initials - set("bpmfjqxw") - {'sh'}:
        table[initial].append("ong")
    # ua
    for initial in set("gkhr") | {'zh', 'ch', 'sh'}:
        table[initial].append("ua")
    # uo
    for initial in all_initials - set("bpmfjqxwy"):
        table[initial].append("uo")
    # uai
    # uang
    for initial in all_initials - set("bpmfdtnlzcsrjqxwy"):
        table[initial].append("uai")
        table[initial].append("uang")
    # ui
    for initial in all_initials - set("bpmfnljqxwy"):
        table[initial].append("ui")
    # uan
    # un
    for initial in all_initials - set("bpmfjqxw"):
        table[initial].append("uan")
        table[initial].append("un")
    # i
    for initial in all_initials - set("fgkhw"):
        table[initial].append("i")
    # ia
    for initial in set("dljqx"):
        table[initial].append("ia")
    # ie
    # iao
    # ian
    for initial in set("bpmdtnljqx"):
        table[initial].append("ie")
        table[initial].append("iao")
        table[initial].append("ian")
    # iu
    for initial in set("mdnljqx"):
        table[initial].append("iu")
    # iang
    for initial in set("nljqx"):
        table[initial].append("iang")
    # in
    for initial in set("bpmnljqxy"):
        table[initial].append("in")
    # ing
    for initial in set("bpmdtnljqxy"):
        table[initial].append("ing")
    # iong
    # ue
    for initial in set("jqxy"):
        table[initial].append("iong")
        table[initial].append("ue")
    # v
    # ve
    for initial in set("nl"):
        table[initial].append("v")
        table[initial].append("ve")

    return table


valid_pinyin = tabulate_pinyin()
