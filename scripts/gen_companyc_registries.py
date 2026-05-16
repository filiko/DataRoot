"""
Generate CompanyC GeneticEngineering registry CSV files:
  - gene_target_catalog.csv   (30 rows)
  - guide_rna_library.csv     (120 rows)
  - cell_line_registry.csv    (25 rows)
"""
import csv
import random
import os

random.seed(42)

BASE_DIR = r"C:\Users\ajfil\Documents\Github\DataRoot\ExampleData\CompanyC_GeneticEngineering\raw\registries"

# ── helpers ───────────────────────────────────────────────────────────────────

def random_seq_with_gc(length: int, gc_pct: int) -> str:
    """Return a random DNA sequence of given length with approximate GC%."""
    gc_count = round(length * gc_pct / 100)
    at_count = length - gc_count
    bases = random.choices(["G", "C"], k=gc_count) + random.choices(["A", "T"], k=at_count)
    random.shuffle(bases)
    return "".join(bases)

def make_ngg_pam() -> str:
    return random.choice("ACGT") + "GG"

def make_nngrrt_pam() -> str:
    n1 = random.choice("ACGT")
    n2 = random.choice("ACGT")
    g = "G"
    r = random.choice("AG")
    return n1 + n2 + g + r + "RT"

# ── 1. gene_target_catalog.csv ────────────────────────────────────────────────

gene_rows = [
    # Arabidopsis thaliana (8)
    {"gene_id":"GENE-001","gene_symbol":"FT","ensembl_id":"AT1G65480",
     "organism":"Arabidopsis thaliana","tissue_expression":"leaf,vasculature",
     "functional_pathway":"photoperiod flowering",
     "edit_rationale":"Delay flowering for biomass increase",
     "target_category":"trait_improvement","notes":"CONSTANS-regulated florigen"},
    {"gene_id":"GENE-002","gene_symbol":"AP1","ensembl_id":"AT1G69120",
     "organism":"Arabidopsis thaliana","tissue_expression":"floral meristem",
     "functional_pathway":"floral development",
     "edit_rationale":"Study meristem identity switching",
     "target_category":"biosafety_validation","notes":"MADS-box transcription factor"},
    {"gene_id":"GENE-003","gene_symbol":"CESA1","ensembl_id":"AT4G32410",
     "organism":"Arabidopsis thaliana","tissue_expression":"stem,hypocotyl",
     "functional_pathway":"cell wall biosynthesis",
     "edit_rationale":"Reduce cellulose crystallinity for saccharification",
     "target_category":"trait_improvement","notes":"Primary wall cellulose synthase A1"},
    {"gene_id":"GENE-004","gene_symbol":"ABI3","ensembl_id":"AT3G24650",
     "organism":"Arabidopsis thaliana","tissue_expression":"seed",
     "functional_pathway":"ABA signaling",
     "edit_rationale":"Enhance desiccation tolerance via ABA hypersensitivity",
     "target_category":"trait_improvement","notes":"B3 domain transcription factor"},
    {"gene_id":"GENE-005","gene_symbol":"JAZ1","ensembl_id":"AT1G19180",
     "organism":"Arabidopsis thaliana","tissue_expression":"ubiquitous",
     "functional_pathway":"jasmonate signaling",
     "edit_rationale":"Constitutive defense pathway activation",
     "target_category":"trait_improvement","notes":"Jasmonate ZIM-domain repressor 1"},
    {"gene_id":"GENE-006","gene_symbol":"FLC","ensembl_id":"AT5G10140",
     "organism":"Arabidopsis thaliana","tissue_expression":"leaf,apex",
     "functional_pathway":"vernalization",
     "edit_rationale":"Accelerate flowering in winter annual backgrounds",
     "target_category":"trait_improvement","notes":"Major floral repressor; H3K27me3 target"},
    {"gene_id":"GENE-007","gene_symbol":"RPS5","ensembl_id":"AT1G12220",
     "organism":"Arabidopsis thaliana","tissue_expression":"leaf",
     "functional_pathway":"innate immunity",
     "edit_rationale":"Broaden NBS-LRR resistance spectrum",
     "target_category":"trait_improvement","notes":"Resistance to Pseudomonas syringae"},
    {"gene_id":"GENE-008","gene_symbol":"GI","ensembl_id":"AT1G22770",
     "organism":"Arabidopsis thaliana","tissue_expression":"leaf",
     "functional_pathway":"circadian clock",
     "edit_rationale":"Photoperiod-independent flowering study",
     "target_category":"trait_improvement","notes":"Gigantea protein; clock component"},
    # Nicotiana benthamiana (6)
    {"gene_id":"GENE-009","gene_symbol":"NbSGT1","ensembl_id":"NbS00000001g0008",
     "organism":"Nicotiana benthamiana","tissue_expression":"ubiquitous",
     "functional_pathway":"innate immunity",
     "edit_rationale":"Immune suppression for stable transient expression",
     "target_category":"production_enhancement","notes":"HSP90 co-chaperone; required for NLR function"},
    {"gene_id":"GENE-010","gene_symbol":"NbRAR1","ensembl_id":"NbS00000002g0004",
     "organism":"Nicotiana benthamiana","tissue_expression":"ubiquitous",
     "functional_pathway":"R protein stability",
     "edit_rationale":"Modify R protein-mediated hypersensitive response",
     "target_category":"biosafety_validation","notes":"CHORD-domain zinc-finger protein"},
    {"gene_id":"GENE-011","gene_symbol":"NbPDS","ensembl_id":"NbS00000003g0012",
     "organism":"Nicotiana benthamiana","tissue_expression":"leaf,chloroplast",
     "functional_pathway":"carotenoid biosynthesis",
     "edit_rationale":"Photobleaching visual marker for editing efficiency",
     "target_category":"biosafety_validation","notes":"Phytoene desaturase; albino knockout marker"},
    {"gene_id":"GENE-012","gene_symbol":"NbRDR6","ensembl_id":"NbS00000004g0006",
     "organism":"Nicotiana benthamiana","tissue_expression":"leaf",
     "functional_pathway":"RNA silencing",
     "edit_rationale":"Reduce PTGS to improve transgene expression stability",
     "target_category":"production_enhancement","notes":"RNA-dependent RNA polymerase 6"},
    {"gene_id":"GENE-013","gene_symbol":"NbACT","ensembl_id":"NbS00000005g0003",
     "organism":"Nicotiana benthamiana","tissue_expression":"ubiquitous",
     "functional_pathway":"cytoskeletal dynamics",
     "edit_rationale":"Reference gene normalization validation",
     "target_category":"biosafety_validation","notes":"Actin; housekeeping reference control"},
    {"gene_id":"GENE-014","gene_symbol":"NbCLA1","ensembl_id":"NbS00000006g0009",
     "organism":"Nicotiana benthamiana","tissue_expression":"leaf",
     "functional_pathway":"plastid development",
     "edit_rationale":"Albino marker for chloroplast-targeted editing",
     "target_category":"biosafety_validation","notes":"1-deoxy-D-xylulose 5-phosphate synthase"},
    # Homo sapiens (10)
    {"gene_id":"GENE-015","gene_symbol":"PDCD1","ensembl_id":"ENSG00000188389",
     "organism":"Homo sapiens","tissue_expression":"T cells,B cells",
     "functional_pathway":"immune checkpoint",
     "edit_rationale":"Enhance T cell anti-tumor activity for CAR-T therapy",
     "target_category":"disease_model","notes":"PD-1; validated clinical CAR-T target"},
    {"gene_id":"GENE-016","gene_symbol":"CD274","ensembl_id":"ENSG00000120217",
     "organism":"Homo sapiens","tissue_expression":"tumor,immune cells",
     "functional_pathway":"immune checkpoint",
     "edit_rationale":"Model PD-L1 knockout tumor lines",
     "target_category":"disease_model","notes":"PD-L1; PD-1 ligand"},
    {"gene_id":"GENE-017","gene_symbol":"BRCA1","ensembl_id":"ENSG00000012048",
     "organism":"Homo sapiens","tissue_expression":"breast,ovary",
     "functional_pathway":"DNA damage repair",
     "edit_rationale":"Cancer predisposition cell line model",
     "target_category":"disease_model","notes":"BRCA1 frameshift allele generation"},
    {"gene_id":"GENE-018","gene_symbol":"KRAS","ensembl_id":"ENSG00000133703",
     "organism":"Homo sapiens","tissue_expression":"pancreas,lung,colon",
     "functional_pathway":"RAS-MAPK signaling",
     "edit_rationale":"G12D/G12V oncogenic allele knock-in",
     "target_category":"disease_model","notes":"Most frequently mutated oncogene"},
    {"gene_id":"GENE-019","gene_symbol":"TP53","ensembl_id":"ENSG00000141510",
     "organism":"Homo sapiens","tissue_expression":"ubiquitous",
     "functional_pathway":"apoptosis",
     "edit_rationale":"Tumor suppressor loss-of-function model",
     "target_category":"disease_model","notes":"R175H hotspot mutation model"},
    {"gene_id":"GENE-020","gene_symbol":"PCSK9","ensembl_id":"ENSG00000169174",
     "organism":"Homo sapiens","tissue_expression":"liver",
     "functional_pathway":"lipid metabolism",
     "edit_rationale":"LDL cholesterol lowering via KO",
     "target_category":"disease_model","notes":"Therapeutic target; base editing validated"},
    {"gene_id":"GENE-021","gene_symbol":"TRAC","ensembl_id":"ENSG00000277734",
     "organism":"Homo sapiens","tissue_expression":"T cells",
     "functional_pathway":"T cell receptor signaling",
     "edit_rationale":"TCR disruption for allogeneic CAR-T manufacturing",
     "target_category":"production_enhancement","notes":"TCR alpha constant region locus"},
    {"gene_id":"GENE-022","gene_symbol":"B2M","ensembl_id":"ENSG00000166710",
     "organism":"Homo sapiens","tissue_expression":"ubiquitous",
     "functional_pathway":"MHC class I presentation",
     "edit_rationale":"HLA class I reduction for universal cell line",
     "target_category":"production_enhancement","notes":"Beta-2 microglobulin"},
    {"gene_id":"GENE-023","gene_symbol":"DNMT3A","ensembl_id":"ENSG00000119772",
     "organism":"Homo sapiens","tissue_expression":"hematopoietic",
     "functional_pathway":"epigenetic regulation",
     "edit_rationale":"AML clonal hematopoiesis disease model",
     "target_category":"disease_model","notes":"DNA methyltransferase 3A; R882H hotspot"},
    {"gene_id":"GENE-024","gene_symbol":"HBB","ensembl_id":"ENSG00000244734",
     "organism":"Homo sapiens","tissue_expression":"erythroid",
     "functional_pathway":"oxygen transport",
     "edit_rationale":"Sickle cell and beta-thalassemia correction",
     "target_category":"disease_model","notes":"E6V sickle mutation; HDR repair template tested"},
    # Mus musculus (6)
    {"gene_id":"GENE-025","gene_symbol":"Trp53","ensembl_id":"ENSMUSG00000059552",
     "organism":"Mus musculus","tissue_expression":"ubiquitous",
     "functional_pathway":"apoptosis",
     "edit_rationale":"Mouse tumor model generation",
     "target_category":"disease_model","notes":"Mouse p53 ortholog; R172H hotspot"},
    {"gene_id":"GENE-026","gene_symbol":"Pcsk9","ensembl_id":"ENSMUSG00000058335",
     "organism":"Mus musculus","tissue_expression":"liver",
     "functional_pathway":"lipid metabolism",
     "edit_rationale":"In vivo liver base editing validation",
     "target_category":"disease_model","notes":"Mouse PCSK9 ortholog"},
    {"gene_id":"GENE-027","gene_symbol":"Trac","ensembl_id":"ENSMUSG00000076928",
     "organism":"Mus musculus","tissue_expression":"T cells",
     "functional_pathway":"T cell receptor signaling",
     "edit_rationale":"Murine allogeneic immune cell engineering",
     "target_category":"disease_model","notes":"Mouse TCR alpha constant region"},
    {"gene_id":"GENE-028","gene_symbol":"Rosa26","ensembl_id":"ENSMUSG00000086503",
     "organism":"Mus musculus","tissue_expression":"ubiquitous",
     "functional_pathway":"safe harbor locus",
     "edit_rationale":"Knock-in landing pad for reporter cassettes",
     "target_category":"production_enhancement","notes":"Mouse safe harbor; ubiquitous expression"},
    {"gene_id":"GENE-029","gene_symbol":"Hprt","ensembl_id":"ENSMUSG00000025630",
     "organism":"Mus musculus","tissue_expression":"ubiquitous",
     "functional_pathway":"purine salvage",
     "edit_rationale":"Selection marker locus; HAT/6-TG counter-selection",
     "target_category":"biosafety_validation","notes":"X-linked; HAT selection compatible"},
    {"gene_id":"GENE-030","gene_symbol":"Pten","ensembl_id":"ENSMUSG00000013663",
     "organism":"Mus musculus","tissue_expression":"brain,prostate",
     "functional_pathway":"PI3K-AKT signaling",
     "edit_rationale":"Tumor suppressor conditional loss model",
     "target_category":"disease_model","notes":"PTEN phosphatase KO; Cre-inducible allele"},
]

gene_fields = ["gene_id","gene_symbol","ensembl_id","organism","tissue_expression",
               "functional_pathway","edit_rationale","target_category","notes"]

out_gene = os.path.join(BASE_DIR, "gene_target_catalog.csv")
with open(out_gene, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=gene_fields)
    w.writeheader()
    w.writerows(gene_rows)
print(f"[1/3] gene_target_catalog.csv  -> {len(gene_rows)} rows")

# ── 2. guide_rna_library.csv ─────────────────────────────────────────────────
# 120 guides, 4 guides per gene (30 genes), mix of SpCas9 (NGG) and SaCas9 (NNGRRT)
# SaCas9 used primarily for mammalian targets (GENE-015..GENE-024, GENE-025..GENE-030 some)
DESIGN_TOOLS = ["CRISPRscan", "Benchling CRISPR", "CHOPCHOP", "CRISPOR", "Cas-OFFinder+scoring"]
STATUSES = ["active", "active", "active", "in_testing", "in_testing", "deprecated", "failed_cloning"]

# assign Cas9 type: SpCas9 for plant targets, mix for mammalian
def cas9_type(gene_idx: int) -> str:
    # gene indices 0-13 → plant → SpCas9; 14-29 → mammalian → mix
    if gene_idx < 14:
        return "SpCas9"
    return "SpCas9" if (gene_idx + random.randint(0,1)) % 2 == 0 else "SaCas9"

guide_rows = []
guide_counter = 1
for gene_idx, gene in enumerate(gene_rows):
    cas = cas9_type(gene_idx)
    for guide_num in range(4):
        gid = f"GRN-{guide_counter:04d}"
        guide_counter += 1
        gc = random.randint(35, 70)
        spacer = random_seq_with_gc(20, gc)
        pam = make_ngg_pam() if cas == "SpCas9" else make_nngrrt_pam()
        strand = random.choice(["+", "-"])
        score = round(random.uniform(0.25, 0.95), 4)
        off_targets = random.randint(0, 12)
        tool = random.choice(DESIGN_TOOLS)
        year = random.randint(2020, 2024)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        design_date = f"{year}-{month:02d}-{day:02d}"
        # Weight toward active
        status = random.choices(
            ["active","in_testing","deprecated","failed_cloning"],
            weights=[0.55, 0.25, 0.12, 0.08]
        )[0]
        notes = f"Cas9 variant: {cas}; exon target: exon {random.randint(1,12)}"
        guide_rows.append({
            "guide_id": gid,
            "target_gene_symbol": gene["gene_symbol"],
            "target_gene_id": gene["gene_id"],
            "spacer_sequence_20nt": spacer,
            "pam_sequence": pam,
            "strand": strand,
            "gc_pct": gc,
            "on_target_score_rs2": score,
            "predicted_off_target_count": off_targets,
            "design_tool": tool,
            "design_date": design_date,
            "status": status,
            "notes": notes,
        })

guide_fields = ["guide_id","target_gene_symbol","target_gene_id","spacer_sequence_20nt",
                "pam_sequence","strand","gc_pct","on_target_score_rs2",
                "predicted_off_target_count","design_tool","design_date","status","notes"]

out_guide = os.path.join(BASE_DIR, "guide_rna_library.csv")
with open(out_guide, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=guide_fields)
    w.writeheader()
    w.writerows(guide_rows)
print(f"[2/3] guide_rna_library.csv    -> {len(guide_rows)} rows")

# ── 3. cell_line_registry.csv ─────────────────────────────────────────────────
cell_rows = [
    # HEK293T
    {"cell_line_id":"CL-001","name":"HEK293T","species":"Homo sapiens",
     "tissue_origin":"embryonic kidney","disease_context":"none (HEK; transformed)",
     "passage_number_received":12,"passage_range_used":"12-35",
     "authentication_method":"STR profiling","authentication_date":"2022-03-15",
     "source_vendor":"ATCC (CRL-3216)","mycoplasma_status":"negative",
     "notes":"High transfection efficiency; lentiviral packaging host"},
    # HeLa
    {"cell_line_id":"CL-002","name":"HeLa","species":"Homo sapiens",
     "tissue_origin":"cervical carcinoma","disease_context":"cervical cancer (HPV18+)",
     "passage_number_received":25,"passage_range_used":"25-50",
     "authentication_method":"STR profiling","authentication_date":"2022-04-10",
     "source_vendor":"ATCC (CCL-2)","mycoplasma_status":"negative",
     "notes":"Classic model; HeLa Kyoto subline preferred for imaging"},
    # Jurkat
    {"cell_line_id":"CL-003","name":"Jurkat E6-1","species":"Homo sapiens",
     "tissue_origin":"T lymphoblast","disease_context":"acute T cell leukemia",
     "passage_number_received":8,"passage_range_used":"8-25",
     "authentication_method":"STR profiling","authentication_date":"2022-05-20",
     "source_vendor":"ATCC (TIB-152)","mycoplasma_status":"negative",
     "notes":"TCR signaling model; PDCD1 KO experiments"},
    # K562
    {"cell_line_id":"CL-004","name":"K562","species":"Homo sapiens",
     "tissue_origin":"bone marrow","disease_context":"chronic myelogenous leukemia",
     "passage_number_received":15,"passage_range_used":"15-40",
     "authentication_method":"STR profiling","authentication_date":"2022-06-01",
     "source_vendor":"ATCC (CCL-243)","mycoplasma_status":"negative",
     "notes":"BCR-ABL+ CML model; HBB editing platform"},
    # HAP1
    {"cell_line_id":"CL-005","name":"HAP1","species":"Homo sapiens",
     "tissue_origin":"chronic myelogenous leukemia (near-haploid)","disease_context":"CML-derived haploid",
     "passage_number_received":5,"passage_range_used":"5-18",
     "authentication_method":"STR profiling","authentication_date":"2022-07-12",
     "source_vendor":"Horizon Discovery","mycoplasma_status":"negative",
     "notes":"Near-haploid; simplifies recessive KO screening"},
    # U2OS
    {"cell_line_id":"CL-006","name":"U2OS","species":"Homo sapiens",
     "tissue_origin":"osteosarcoma","disease_context":"osteosarcoma",
     "passage_number_received":18,"passage_range_used":"18-45",
     "authentication_method":"STR profiling","authentication_date":"2022-08-05",
     "source_vendor":"ATCC (HTB-96)","mycoplasma_status":"negative",
     "notes":"Good nuclear spreading; used for HDR template optimization"},
    # MCF7
    {"cell_line_id":"CL-007","name":"MCF-7","species":"Homo sapiens",
     "tissue_origin":"breast adenocarcinoma","disease_context":"breast cancer (ER+)",
     "passage_number_received":22,"passage_range_used":"22-50",
     "authentication_method":"STR profiling","authentication_date":"2022-09-18",
     "source_vendor":"ATCC (HTB-22)","mycoplasma_status":"negative",
     "notes":"BRCA1 editing target; ER-positive background"},
    # Primary T cells - CD4
    {"cell_line_id":"CL-008","name":"Primary CD4+ T cells (donor 01)","species":"Homo sapiens",
     "tissue_origin":"peripheral blood","disease_context":"healthy donor",
     "passage_number_received":0,"passage_range_used":"0-3 (days 0-14 post-activation)",
     "authentication_method":"flow cytometry (CD3/CD4/CD8)","authentication_date":"2023-01-10",
     "source_vendor":"Internal apheresis (IRB-2022-045)","mycoplasma_status":"negative",
     "notes":"PDCD1/TRAC dual KO CAR-T manufacturing; activated D0 with anti-CD3/CD28"},
    # Primary T cells - CD8
    {"cell_line_id":"CL-009","name":"Primary CD8+ T cells (donor 02)","species":"Homo sapiens",
     "tissue_origin":"peripheral blood","disease_context":"healthy donor",
     "passage_number_received":0,"passage_range_used":"0-3 (days 0-14 post-activation)",
     "authentication_method":"flow cytometry (CD3/CD4/CD8)","authentication_date":"2023-02-14",
     "source_vendor":"Internal apheresis (IRB-2022-045)","mycoplasma_status":"negative",
     "notes":"Cytotoxic T cell model; B2M KO universalization experiments"},
    # Primary fibroblasts
    {"cell_line_id":"CL-010","name":"Primary dermal fibroblasts (donor 03)","species":"Homo sapiens",
     "tissue_origin":"dermis","disease_context":"healthy donor",
     "passage_number_received":2,"passage_range_used":"2-8",
     "authentication_method":"morphology + vimentin IHC","authentication_date":"2023-03-05",
     "source_vendor":"LONZA (CC-2511)","mycoplasma_status":"negative",
     "notes":"iPSC reprogramming base; DNMT3A editing validation"},
    # iPSC
    {"cell_line_id":"CL-011","name":"WTC-11 iPSC","species":"Homo sapiens",
     "tissue_origin":"iPSC (derived from fibroblast)","disease_context":"none (healthy)",
     "passage_number_received":30,"passage_range_used":"30-55",
     "authentication_method":"STR profiling + pluripotency markers","authentication_date":"2023-04-22",
     "source_vendor":"Coriell (GM25256)","mycoplasma_status":"negative",
     "notes":"Feeder-free E8 medium; Rosa26-targeted knock-in validation"},
    # HCT116
    {"cell_line_id":"CL-012","name":"HCT116","species":"Homo sapiens",
     "tissue_origin":"colorectal carcinoma","disease_context":"colorectal cancer (KRAS G13D)",
     "passage_number_received":10,"passage_range_used":"10-30",
     "authentication_method":"STR profiling","authentication_date":"2023-05-08",
     "source_vendor":"ATCC (CCL-247)","mycoplasma_status":"negative",
     "notes":"KRAS G13D endogenous; used for KRAS allele-specific editing"},
    # Panc1
    {"cell_line_id":"CL-013","name":"PANC-1","species":"Homo sapiens",
     "tissue_origin":"pancreatic ductal carcinoma","disease_context":"pancreatic cancer (KRAS G12D)",
     "passage_number_received":14,"passage_range_used":"14-35",
     "authentication_method":"STR profiling","authentication_date":"2023-06-15",
     "source_vendor":"ATCC (CRL-1469)","mycoplasma_status":"negative",
     "notes":"KRAS G12D endogenous model; hard to transfect; electroporation required"},
    # THP-1
    {"cell_line_id":"CL-014","name":"THP-1","species":"Homo sapiens",
     "tissue_origin":"monocyte (acute monocytic leukemia)","disease_context":"AML",
     "passage_number_received":9,"passage_range_used":"9-25",
     "authentication_method":"STR profiling","authentication_date":"2023-07-02",
     "source_vendor":"ATCC (TIB-202)","mycoplasma_status":"negative",
     "notes":"DNMT3A editing model; PMA-differentiable to macrophage"},
    # NIH3T3 (mouse)
    {"cell_line_id":"CL-015","name":"NIH 3T3","species":"Mus musculus",
     "tissue_origin":"embryonic fibroblast","disease_context":"none (immortalized)",
     "passage_number_received":20,"passage_range_used":"20-45",
     "authentication_method":"karyotyping","authentication_date":"2023-01-18",
     "source_vendor":"ATCC (CRL-1658)","mycoplasma_status":"negative",
     "notes":"Mouse fibroblast standard; Trp53 editing platform"},
    # C2C12 (mouse myoblast)
    {"cell_line_id":"CL-016","name":"C2C12","species":"Mus musculus",
     "tissue_origin":"myoblast","disease_context":"none (immortalized)",
     "passage_number_received":11,"passage_range_used":"11-28",
     "authentication_method":"karyotyping","authentication_date":"2023-02-20",
     "source_vendor":"ATCC (CRL-1772)","mycoplasma_status":"negative",
     "notes":"Differentiation to myotubes; Pten KO muscle model"},
    # Mouse primary hepatocytes
    {"cell_line_id":"CL-017","name":"Primary mouse hepatocytes (C57BL/6)","species":"Mus musculus",
     "tissue_origin":"liver","disease_context":"none (wild-type C57BL/6)",
     "passage_number_received":0,"passage_range_used":"fresh isolation; 0-2 days",
     "authentication_method":"albumin/ASGPR1 immunostaining","authentication_date":"2023-03-30",
     "source_vendor":"In-house isolation","mycoplasma_status":"negative",
     "notes":"Pcsk9 in vivo base editing follow-up; short viability window"},
    # Neuro2a
    {"cell_line_id":"CL-018","name":"Neuro-2a","species":"Mus musculus",
     "tissue_origin":"neuroblastoma","disease_context":"neuroblastoma",
     "passage_number_received":16,"passage_range_used":"16-40",
     "authentication_method":"karyotyping","authentication_date":"2023-04-12",
     "source_vendor":"ATCC (CCL-131)","mycoplasma_status":"negative",
     "notes":"Pten editing neural context; differentiates to neurons with RA"},
    # Mouse primary T cells
    {"cell_line_id":"CL-019","name":"Primary mouse CD8+ T cells (C57BL/6)","species":"Mus musculus",
     "tissue_origin":"spleen/lymph node","disease_context":"none (wild-type)",
     "passage_number_received":0,"passage_range_used":"0-2 (days 0-10 post-activation)",
     "authentication_method":"flow cytometry (CD3/CD8/CD44)","authentication_date":"2023-05-25",
     "source_vendor":"In-house isolation","mycoplasma_status":"negative",
     "notes":"Trac KO model; OT-I background for antigen-specific assays"},
    # Arabidopsis T87 suspension
    {"cell_line_id":"CL-020","name":"Arabidopsis T87 suspension","species":"Arabidopsis thaliana",
     "tissue_origin":"leaf callus (Columbia-0)","disease_context":"none",
     "passage_number_received":0,"passage_range_used":"subculture weekly",
     "authentication_method":"PCR genotyping (Col-0 markers)","authentication_date":"2023-06-10",
     "source_vendor":"RIKEN BRC (RPC00003)","mycoplasma_status":"N/A (plant)",
     "notes":"FT and FLC editing; agrobacterium competent"},
    # Nicotiana protoplasts
    {"cell_line_id":"CL-021","name":"N. benthamiana leaf protoplasts","species":"Nicotiana benthamiana",
     "tissue_origin":"leaf mesophyll","disease_context":"none",
     "passage_number_received":0,"passage_range_used":"fresh isolation same day",
     "authentication_method":"GFP transient expression viability check","authentication_date":"2023-07-08",
     "source_vendor":"In-house (greenhouse stock)","mycoplasma_status":"N/A (plant)",
     "notes":"NbPDS and NbRDR6 editing; PEG-mediated delivery; 4-6 week-old plants used"},
    # Ramos B cell
    {"cell_line_id":"CL-022","name":"Ramos","species":"Homo sapiens",
     "tissue_origin":"B cell lymphoma","disease_context":"Burkitt lymphoma",
     "passage_number_received":7,"passage_range_used":"7-22",
     "authentication_method":"STR profiling","authentication_date":"2023-08-03",
     "source_vendor":"ATCC (CRL-1596)","mycoplasma_status":"negative",
     "notes":"CD274 (PD-L1) KO model; B cell immune checkpoint studies"},
    # HepG2
    {"cell_line_id":"CL-023","name":"HepG2","species":"Homo sapiens",
     "tissue_origin":"hepatocellular carcinoma","disease_context":"liver cancer",
     "passage_number_received":19,"passage_range_used":"19-45",
     "authentication_method":"STR profiling","authentication_date":"2023-09-14",
     "source_vendor":"ATCC (HB-8065)","mycoplasma_status":"negative",
     "notes":"PCSK9 KO liver model; low transfection efficiency; lipofection optimized"},
    # Mouse ESC
    {"cell_line_id":"CL-024","name":"Bruce4 mESC (C57BL/6)","species":"Mus musculus",
     "tissue_origin":"blastocyst inner cell mass","disease_context":"none",
     "passage_number_received":10,"passage_range_used":"10-25",
     "authentication_method":"karyotyping + Oct4/Nanog IHC","authentication_date":"2023-10-01",
     "source_vendor":"ATCC (SCRC-1002)","mycoplasma_status":"negative",
     "notes":"Rosa26 landing pad KI; feeder-free on gelatin; 2i medium"},
    # HUVEC
    {"cell_line_id":"CL-025","name":"HUVEC (pooled donors)","species":"Homo sapiens",
     "tissue_origin":"umbilical vein endothelium","disease_context":"none (primary)",
     "passage_number_received":2,"passage_range_used":"2-7",
     "authentication_method":"CD31/VWF immunostaining","authentication_date":"2023-11-20",
     "source_vendor":"LONZA (CC-2519A)","mycoplasma_status":"negative",
     "notes":"KRAS/TP53 angiogenesis context; limited passage window; cryopreserved P2"},
]

cell_fields = ["cell_line_id","name","species","tissue_origin","disease_context",
               "passage_number_received","passage_range_used","authentication_method",
               "authentication_date","source_vendor","mycoplasma_status","notes"]

out_cell = os.path.join(BASE_DIR, "cell_line_registry.csv")
with open(out_cell, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=cell_fields)
    w.writeheader()
    w.writerows(cell_rows)
print(f"[3/3] cell_line_registry.csv   -> {len(cell_rows)} rows")

print("\nAll registry files generated successfully.")
