"""Edge case suite for rule engines + pipeline wiring."""
from pipeline.models import PageResult, PageOCR
from pipeline.assemble import populate_row_for_package
from pipeline.schemas import EXTRA_DOCUMENT_RANK
from rules.mg064a_anemia import evaluate_page_mg064a
from rules.mg006a_enteric import evaluate_page_mg006a
from rules.sb039a_tkr import evaluate_page_sb039a
from rules.sg039c_cholecystectomy import evaluate_page_sg039c


def _pr(doc_type, text, page_number=1, file_name="d.pdf", quality=None):
    pr = PageResult(case_id="C1", file_name=file_name, page_number=page_number,
                    ocr=PageOCR(text=text, lines=[]), doc_type=doc_type,
                    doc_type_confidence=0.9)
    if quality:
        pr.quality = quality
    return pr


def test_mg064a_hb_11_2_no_severe_anemia():
    pr = _pr("cbc_hb_report", "Haemoglobin 11.2 g/dL")
    r = {x.field_name: x.value for x in evaluate_page_mg064a(pr)}
    assert r["severe_anemia"] == 0


def test_mg064a_hb_5_8_severe_anemia_with_evidence():
    pr = _pr("cbc_hb_report", "Haemoglobin 5.8 g/dL\nMCV 70")
    results = evaluate_page_mg064a(pr)
    rd = {x.field_name: x for x in results}
    assert rd["severe_anemia"].value == 1
    assert rd["severe_anemia"].evidence, "positive flag must carry evidence"


def test_dod_before_doa_still_extracted():
    pr = _pr("discharge_summary",
             "Date of Admission: 18-03-2026\nDate of Discharge: 12-03-2026")
    evaluate_page_sb039a(pr)
    # Phase 2 does not check timeline validity; just extracts
    assert pr.entities.get("doa") == "18-03-2026"
    assert pr.entities.get("dod") == "12-03-2026"


def test_missing_ocr_classifies_unknown():
    pr = _pr("unknown", "")
    row = populate_row_for_package("MG064A", pr, rule_results=evaluate_page_mg064a(pr))
    assert row["extra_document"] == 1
    assert row["document_rank"] == EXTRA_DOCUMENT_RANK


def test_mg006a_temp_99_no_fever():
    pr = _pr("clinical_notes", "Temperature 99 F, patient feels fine.")
    r = {x.field_name: x.value for x in evaluate_page_mg006a(pr)}
    assert r["fever"] == 0


def test_mg006a_temp_103_fever_with_evidence():
    pr = _pr("clinical_notes", "Temperature 103 F for 2 days")
    rs = evaluate_page_mg006a(pr)
    rd = {x.field_name: x for x in rs}
    assert rd["fever"].value == 1
    assert rd["fever"].evidence


def test_sb039a_age_45_invalid():
    pr = _pr("clinical_notes", "Age: 45 years")
    r = {x.field_name: x.value for x in evaluate_page_sb039a(pr)}
    assert r["age_valid"] == 0


def test_sb039a_age_67_valid_with_evidence():
    pr = _pr("clinical_notes", "Age: 67 years, male")
    rs = evaluate_page_sb039a(pr)
    rd = {x.field_name: x for x in rs}
    assert rd["age_valid"].value == 1
    assert rd["age_valid"].evidence


def test_sg039c_usg_calculi_fires():
    pr = _pr("usg_report", "USG abdomen: calculi in gall bladder")
    rs = evaluate_page_sg039c(pr)
    rd = {x.field_name: x for x in rs}
    assert rd["usg_calculi"].value == 1
    assert rd["usg_calculi"].evidence


def test_mg064a_common_and_significant_signs_both_fire():
    pr = _pr("clinical_notes",
             "Patient has pallor and breathless on exertion.")
    rs = evaluate_page_mg064a(pr)
    rd = {x.field_name: x.value for x in rs}
    assert rd["common_signs"] == 1
    assert rd["significant_signs"] == 1
