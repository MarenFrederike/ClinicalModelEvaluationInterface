"""
Seed the database with real cases sourced from Radiopaedia (radiopaedia.org).
Runs on application startup; skips if data already exists.
Each case gets two AI model outputs so clinicians have something to compare and evaluate.
Key images are downloaded from the Radiopaedia CDN and stored as BLOB in the database.
"""

import urllib.request
from typing import Optional

from sqlalchemy.orm import Session
from app.models import Case, ModelOutput


def _fetch_image(url: str) -> Optional[bytes]:
    """Fetch image from url, return bytes on success or None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Case data — sourced from Radiopaedia
# image_url: CDN JPEG to download and store as BLOB in the database
# image_path: Radiopaedia viewer URL — always stored for the external link
# ---------------------------------------------------------------------------

CASES = [
    {
        "title": "Retroperitoneal Leiomyosarcoma",
        "modality": "CT",
        "patient_age": 70, "patient_sex": "F",
        "image_url": "https://prod-images-static.radiopaedia.org/images/31127369/7a2d8584ede11f0f8a8ce28f60cb09_gallery.jpeg",
        "image_path": "https://radiopaedia.org/cases/54211/studies/60403",
        "clinical_prompt": (
            "70-year-old female. Follow-up imaging for known stage IV retroperitoneal "
            "leiomyosarcoma with lung metastasis, pathologically confirmed approximately "
            "2 years prior. Patient reports worsening right flank pain. "
            "Please report the contrast-enhanced CT of the abdomen and chest."
        ),
    },
    {
        "title": "Right MCA Territory Infarct with Dense MCA Sign",
        "modality": "CT",
        "patient_age": 65, "patient_sex": "F",
        "image_url": "https://prod-images-static.radiopaedia.org/images/74247943/dr-gallery.jpg",
        "image_path": "https://radiopaedia.org/cases/231191/studies/177152",
        "clinical_prompt": (
            "65-year-old female presenting with acute onset left-sided body weakness. "
            "Non-contrast CT of the head performed on arrival to the emergency department. "
            "Please report the scan and comment on any signs of large vessel occlusion."
        ),
    },
    {
        "title": "Lung Adenocarcinoma",
        "modality": "CT",
        "patient_age": 65, "patient_sex": "M",
        "image_url": "https://prod-images-static.radiopaedia.org/images/74189328/158f4a1963cfcbc8b4a98d9bd4938f03e5670534b83118abb7d7c3987b6e8cd9_gallery.jpeg",
        "image_path": "https://radiopaedia.org/cases/230721/studies/176929",
        "clinical_prompt": (
            "65-year-old male, heavy smoker, presenting with left-sided chest pain and "
            "progressive dyspnoea over the past 3 months. Contrast-enhanced CT of the "
            "chest performed. Please provide a full report including staging assessment."
        ),
    },
    {
        "title": "Neurovascular Compression Syndrome — Trigeminal Nerve",
        "modality": "MRI",
        "patient_age": 80, "patient_sex": "F",
        "image_url": "https://prod-images-static.radiopaedia.org/images/73769637/dr-gallery.jpg",
        "image_path": "https://radiopaedia.org/cases/228001/studies/175206",
        "clinical_prompt": (
            "80-year-old female with chronic left-sided facial pain of sudden onset, "
            "severe intensity, spreading across the jaw, cheek, and periorbital region. "
            "Clinical diagnosis of trigeminal neuralgia queried. MRI of the brain with "
            "dedicated thin-slice CISS/FIESTA sequence through the posterior fossa requested. "
            "Please report with specific attention to the trigeminal nerve."
        ),
    },
    {
        "title": "Croup (Inverted V / Steeple Sign)",
        "modality": "X-ray",
        "patient_age": 3, "patient_sex": "M",
        "image_url": "https://prod-images-static.radiopaedia.org/images/74182875/5e8c4e15d13cab8ea8ff02f7349da84696f2b6e0a9288039e6f51cf084f5643e_gallery.jpeg",
        "image_path": "https://radiopaedia.org/cases/230756/studies/176947",
        "clinical_prompt": (
            "3-year-old male presenting with 2-day history of barking cough and inspiratory "
            "stridor. Afebrile. No drooling. Frontal and lateral plain radiographs of the "
            "chest and neck obtained. Please report with attention to the upper airway."
        ),
    },
    {
        "title": "Abdominal Compartment Syndrome Secondary to Hepatic Haemangioma",
        "modality": "CT",
        "patient_age": 3, "patient_sex": "M",
        "image_url": "https://prod-images-static.radiopaedia.org/images/73968924/ef314b4b32c153d55cc4e265130decdb8bb4ab86532dc9a152e0167cbbf014c1_gallery.jpeg",
        "image_path": "https://radiopaedia.org/cases/229292/studies/176099",
        "clinical_prompt": (
            "3-year-old male with biopsy-confirmed infantile hepatic haemangioma on "
            "propranolol therapy, previously worked up for liver transplantation. "
            "Re-presents with acute abdominal distension, pain, and signs of hypovolaemic "
            "shock. Portovenous phase contrast-enhanced CT of the abdomen performed. "
            "Please report urgently."
        ),
    },
]


# ---------------------------------------------------------------------------
# AI model outputs — two models per case, intentionally varied so evaluators
# have a meaningful comparison task.
# Model A tends to be verbose; Model B is more concise but may under-report.
# ---------------------------------------------------------------------------

OUTPUTS = {
    "Retroperitoneal Leiomyosarcoma": [
        {
            "model_name": "DECIPHER-M", "model_version": "v1",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Retroperitoneum: There is a progressive heterogeneous, predominantly hypodense "
                "retroperitoneal mass in the right retroperitoneum with internal calcifications. "
                "The lesion demonstrates worsening circumferential involvement of the right ureter "
                "extending to the renal pelvis, resulting in mild-to-moderate right-sided "
                "hydronephrosis. The long axis of the mass is oriented parallel to the IVC with "
                "loss of the intervening fat plane, raising the possibility of IVC origin.\n\n"
                "Peritoneum: At least two new peritoneal soft tissue nodules are identified since "
                "prior imaging, in keeping with peritoneal disease progression.\n\n"
                "Chest: Bilateral pulmonary nodules are increased in size and number compared with "
                "prior examination. The dominant nodule in the right lower lobe has enlarged. "
                "Findings are consistent with progressive pulmonary metastatic disease.\n\n"
                "Lymph nodes: No significant lymphadenopathy identified.\n"
                "Abdomen: Gallbladder calculi noted. Bilateral simple renal cortical cysts. "
                "No ascites.\n\n"
                "IMPRESSION:\n"
                "1. Progressive stage IV retroperitoneal leiomyosarcoma with increasing right "
                "retroperitoneal mass, new circumferential ureteric involvement causing "
                "hydronephrosis, new peritoneal deposits, and increasing bilateral pulmonary "
                "metastases. Overall disease trajectory is one of significant progression.\n"
                "2. Possible IVC origin of the primary lesion given anatomical relationship.\n"
                "3. Incidental cholelithiasis and bilateral renal cortical cysts."
            ),
        },
        {
            "model_name": "DECIPHER-M", "model_version": "v2",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Retroperitoneum: Progressive enlargement of right retroperitoneal heterogeneous "
                "hypodense mass with internal calcifications. New circumferential encasement of "
                "the right ureter extending to the renal pelvis causing mild hydronephrosis. "
                "Close relationship with the IVC noted.\n\n"
                "Peritoneum: Two new peritoneal nodules identified.\n\n"
                "Lungs: Increased bilateral pulmonary nodules consistent with metastatic "
                "progression. Largest nodule in right lower lobe.\n\n"
                "No lymphadenopathy or ascites. Incidental gallstones and renal cysts.\n\n"
                "IMPRESSION:\n"
                "Progressive stage IV retroperitoneal leiomyosarcoma. Interval increase in "
                "retroperitoneal mass with ureteric obstruction, new peritoneal metastases, "
                "and worsening pulmonary metastatic burden. "
                "Clinical correlation and multidisciplinary review recommended."
            ),
        },
    ],
    "Right MCA Territory Infarct with Dense MCA Sign": [
        {
            "model_name": "DECIPHER-M", "model_version": "v1",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "There is subtle hypoattenuation of the right insular cortex and adjacent "
                "temporal lobe with loss of grey-white matter differentiation, consistent with "
                "the 'insular ribbon sign'. Mild sulcal effacement is noted in the right MCA "
                "territory. The right MCA appears hyperdense compared to the contralateral side, "
                "representing the 'dense MCA sign' indicating thrombotic occlusion.\n\n"
                "ASPECTS score: 9 (isolated insular involvement).\n\n"
                "No acute intracranial haemorrhage. Mild generalised cortical atrophy with "
                "prominent sulci and mild ventriculomegaly, in keeping with age-related changes.\n\n"
                "IMPRESSION:\n"
                "1. Early acute right MCA territory ischaemic infarction with large vessel "
                "occlusion — hyperdense right MCA sign identified.\n"
                "2. ASPECTS 9: Limited early ischaemic change confined to the right insula.\n"
                "3. Findings support consideration for urgent thrombectomy. "
                "Recommend immediate neurovascular team review."
            ),
        },
        {
            "model_name": "DECIPHER-M", "model_version": "v2",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Subtle right insular ribbon sign with early hypoattenuation and sulcal "
                "effacement in the right MCA territory. Hyperdense right MCA consistent with "
                "acute thrombus.\n\n"
                "No haemorrhage. Background age-related atrophy.\n\n"
                "IMPRESSION:\n"
                "Acute right MCA territory infarction with hyperdense MCA sign indicating "
                "large vessel occlusion. ASPECTS 9. "
                "Urgent clinical review required."
            ),
        },
    ],
    "Lung Adenocarcinoma": [
        {
            "model_name": "DECIPHER-M", "model_version": "v1",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Left upper lobe: Large heterogeneous soft tissue mass in the apicoposterior "
                "segment measuring approximately 10.5 × 7.5 × 8.0 cm. The lesion contains "
                "punctate calcifications. No internal fat or fluid attenuation. There is direct "
                "extension to the chest wall via intercostal soft tissues, though no frank "
                "osseous invasion is demonstrated.\n\n"
                "Pleura: Large left-sided loculated pleural effusion measuring up to 9.3 cm "
                "with associated compressive left lower lobe atelectasis.\n\n"
                "Lymph nodes: Enlarged left axillary, phrenic, and paraesophageal lymph nodes "
                "consistent with nodal metastatic spread.\n\n"
                "Contralateral lung: Incidental 0.5 cm nodule in the right lower lobe — "
                "recommend follow-up per Fleischner criteria.\n\n"
                "Abdomen: Cholecystectomy clips and pneumobilia noted as incidental findings.\n\n"
                "IMPRESSION:\n"
                "1. Large left upper lobe apicoposterior mass with chest wall involvement, "
                "extensive ipsilateral pleural effusion, and multi-station nodal spread. "
                "Appearances are highly suspicious for T4 N3 Mx primary lung malignancy.\n"
                "2. Peripheral morphology favours adenocarcinoma or large cell carcinoma.\n"
                "3. Right lower lobe 0.5 cm nodule — indeterminate, follow-up recommended.\n"
                "4. CT-guided biopsy and PET-CT for staging recommended."
            ),
        },
        {
            "model_name": "DECIPHER-M", "model_version": "v2",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Large left apicoposterior upper lobe mass (~10.5 × 8 cm) with chest wall "
                "extension and associated large loculated left pleural effusion. Left lower "
                "lobe atelectasis.\n\n"
                "Enlarged mediastinal and left axillary lymph nodes.\n\n"
                "Small right lower lobe nodule (0.5 cm).\n\n"
                "Incidental post-cholecystectomy changes.\n\n"
                "IMPRESSION:\n"
                "Left upper lobe mass with pleural effusion, chest wall involvement, and nodal "
                "disease — highly suspicious for advanced primary lung carcinoma. "
                "Histological confirmation required. PET-CT and MDT review advised.\n\n"
                "NOTE: Pleural effusion and left lower lobe atelectasis are present but the "
                "report does not exclude malignant pleural involvement — cytological sampling "
                "should be considered."
            ),
        },
    ],
    "Neurovascular Compression Syndrome — Trigeminal Nerve": [
        {
            "model_name": "DECIPHER-M", "model_version": "v1",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Trigeminal nerves: On dedicated thin-section CISS sequences, the cisternal "
                "segment of the left trigeminal nerve demonstrates upward displacement at its "
                "crossing point with the anterior inferior cerebellar artery (AICA). Contact "
                "between the AICA loop and the left trigeminal nerve is identified at the root "
                "entry zone, consistent with neurovascular compression. The right trigeminal "
                "nerve appears normal.\n\n"
                "White matter: Scattered periventricular and subcortical white matter T2/FLAIR "
                "hyperintensities are present, in keeping with chronic small vessel disease.\n\n"
                "Incidental bilateral opercular perivascular spaces noted.\n"
                "Lensectomy changes noted bilaterally. No acute intracranial abnormality.\n\n"
                "IMPRESSION:\n"
                "1. Neurovascular compression of the left trigeminal nerve at the root entry "
                "zone by an AICA loop — consistent with the clinical diagnosis of left "
                "trigeminal neuralgia.\n"
                "2. Background chronic small vessel ischaemic disease.\n"
                "3. Findings support neurosurgical referral for consideration of microvascular "
                "decompression (MVD)."
            ),
        },
        {
            "model_name": "DECIPHER-M", "model_version": "v2",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "CISS sequences demonstrate contact between the AICA and the left trigeminal "
                "nerve at the root entry zone with displacement of the nerve. "
                "Right trigeminal nerve is unremarkable.\n\n"
                "White matter changes consistent with small vessel disease. "
                "Bilateral lensectomy changes. No mass or haemorrhage.\n\n"
                "IMPRESSION:\n"
                "Left trigeminal neurovascular compression by AICA at the root entry zone, "
                "correlating with the clinical presentation of left trigeminal neuralgia. "
                "Neurosurgical opinion recommended.\n\n"
                "NOTE: The model did not comment on the severity of nerve displacement or "
                "whether there is indentation/distortion of the nerve, which may be "
                "relevant for surgical planning."
            ),
        },
    ],
    "Croup (Inverted V / Steeple Sign)": [
        {
            "model_name": "DECIPHER-M", "model_version": "v1",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Upper airway: Frontal radiograph demonstrates symmetric tapering of the "
                "subglottic trachea with loss of the normal shouldered appearance, producing "
                "the characteristic 'steeple sign' (inverted V configuration). Lateral view "
                "confirms uniform subglottic narrowing. No epiglottic thickening or 'thumb sign'.\n\n"
                "Lungs: No focal consolidation, collapse, or air trapping to suggest "
                "foreign body. Lung fields are otherwise clear.\n\n"
                "Soft tissues and bones: No prevertebral soft tissue swelling. "
                "Skeletal maturity appropriate for age.\n\n"
                "IMPRESSION:\n"
                "1. Classic radiographic steeple sign consistent with croup "
                "(laryngotracheobronchitis). Clinical and radiographic findings are concordant.\n"
                "2. No radiographic evidence of epiglottitis, bacterial tracheitis, or "
                "foreign body inhalation.\n"
                "3. Management with corticosteroids and nebulised epinephrine as clinically "
                "indicated. Radiological follow-up not routinely required if clinical "
                "improvement is achieved."
            ),
        },
        {
            "model_name": "DECIPHER-M", "model_version": "v2",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Subglottic tracheal narrowing with steeple/inverted-V sign on frontal view. "
                "Lateral view confirms uniform subglottic narrowing. No epiglottic abnormality.\n\n"
                "Lung fields clear. No foreign body.\n\n"
                "IMPRESSION:\n"
                "Radiographic appearances consistent with croup. "
                "Epiglottitis and foreign body excluded radiographically.\n\n"
                "NOTE: Report does not comment on the degree of airway narrowing or correlate "
                "with oxygen saturation — severity grading (e.g. Westley score) would be "
                "clinically useful in this context."
            ),
        },
    ],
    "Abdominal Compartment Syndrome Secondary to Hepatic Haemangioma": [
        {
            "model_name": "DECIPHER-M", "model_version": "v1",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Liver: Marked hepatomegaly with extensive bilateral hypoattenuating lesions "
                "consistent with known infantile hepatic haemangiomas. An exophytic segment 3 "
                "lesion demonstrates peripheral calcifications and shows contrast pooling "
                "raising concern for active haemorrhage. Internal shunting (aortoportal and/or "
                "venoportal) is suspected based on contrast dynamics.\n\n"
                "Inferior vena cava: The IVC and intrahepatic hepatic veins are compressed by "
                "the markedly enlarged liver.\n\n"
                "Abdomen: Severe abdominopelvic ascites. The diaphragm is significantly "
                "elevated bilaterally. The 'round belly sign' is present — increased AP to "
                "transverse abdominal diameter ratio. Mesentery is congested and hazy.\n\n"
                "No pneumoperitoneum.\n\n"
                "IMPRESSION:\n"
                "1. Markedly enlarged liver with extensive infantile haemangiomas. Features "
                "suggest haemorrhage from the exophytic segment 3 lesion as the precipitant.\n"
                "2. Massive ascites, diaphragmatic elevation, IVC compression, and round belly "
                "sign are consistent with abdominal compartment syndrome.\n"
                "3. URGENT findings — immediate surgical and paediatric ICU review required. "
                "Consideration of emergent paracentesis and/or interventional radiology."
            ),
        },
        {
            "model_name": "DECIPHER-M", "model_version": "v2",
            "output_type": "report",
            "output_text": (
                "FINDINGS:\n"
                "Massive hepatomegaly with bilateral hypodense haemangiomatous lesions. "
                "Exophytic segment 3 lesion with calcifications and contrast pooling — "
                "possible haematoma or active bleed.\n\n"
                "Severe ascites with diaphragmatic elevation and bowel displacement. "
                "Round belly sign present. IVC appears compressed.\n\n"
                "IMPRESSION:\n"
                "Findings consistent with abdominal compartment syndrome in the setting of "
                "known hepatic haemangioma, likely secondary to haemorrhage. "
                "Urgent surgical review required.\n\n"
                "NOTE: The model did not specifically comment on vascular shunting or "
                "characterise all hepatic lesions, which may affect interventional planning."
            ),
        },
    ],
}


def seed(db: Session) -> None:
    if db.query(Case).first():
        return  # already seeded

    for case_data in CASES:
        image_url = case_data.get("image_url", "")
        image_bytes = _fetch_image(image_url) if image_url else None

        case = Case(
            title=case_data["title"],
            modality=case_data["modality"],
            image_path=case_data["image_path"],   # Radiopaedia viewer URL
            image_data=image_bytes,               # downloaded BLOB (None if fetch failed)
            clinical_prompt=case_data["clinical_prompt"],
            patient_age=case_data.get("patient_age"),
            patient_sex=case_data.get("patient_sex"),
        )
        db.add(case)
        db.flush()  # get case.id

        # Outputs are added independently — simulating the model pipeline
        # writing to the DB after running inference on the case.
        for output_data in OUTPUTS[case_data["title"]]:
            output = ModelOutput(
                case_id=case.id,
                model_name=output_data["model_name"],
                model_version=output_data.get("model_version"),
                output_type=output_data["output_type"],
                output_text=output_data["output_text"],
                status="queued",
            )
            db.add(output)

    db.commit()
