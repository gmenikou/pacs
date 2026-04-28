import os
import re
import zipfile
from io import BytesIO

import numpy as np
import pydicom
import requests
import streamlit as st
from PIL import Image


# =========================
# CONFIG
# =========================

DEFAULT_ORTHANC_URL = "http://127.0.0.1:8042"
DEFAULT_DOWNLOAD_DIR = "./dicom_downloads"


# =========================
# HELPERS
# =========================

def safe_name(value):
    value = str(value or "Unknown")
    value = re.sub(r"[^\w\-. ]+", "_", value)
    return value.strip().replace(" ", "_")


def orthanc_get(url, path):
    r = requests.get(f"{url}{path}")
    r.raise_for_status()
    return r.json()


def orthanc_post(url, path, payload):
    r = requests.post(f"{url}{path}", json=payload)
    r.raise_for_status()
    return r.json()


def get_instance_file(url, instance_id):
    r = requests.get(f"{url}/instances/{instance_id}/file")
    r.raise_for_status()
    return r.content


def dicom_to_image(dicom_bytes):
    ds = pydicom.dcmread(BytesIO(dicom_bytes))
    arr = ds.pixel_array.astype(np.float32)

    slope = float(getattr(ds, "RescaleSlope", 1))
    intercept = float(getattr(ds, "RescaleIntercept", 0))
    arr = arr * slope + intercept

    arr = arr - np.min(arr)
    arr = arr / (np.max(arr) + 1e-6)
    arr = (arr * 255).astype(np.uint8)

    return Image.fromarray(arr)


def download_archive(url, level, orthanc_id, destination_folder):
    archive_url = f"{url}/{level}/{orthanc_id}/archive"
    r = requests.get(archive_url)
    r.raise_for_status()

    os.makedirs(destination_folder, exist_ok=True)

    with zipfile.ZipFile(BytesIO(r.content)) as z:
        z.extractall(destination_folder)

    return destination_folder


def get_study_display_name(study):
    main = study.get("MainDicomTags", {})
    patient = study.get("PatientMainDicomTags", {})

    return safe_name(
        f"{patient.get('PatientID','ID')}_"
        f"{patient.get('PatientName','Name')}_"
        f"{main.get('StudyDate','Date')}_"
        f"{main.get('AccessionNumber','Acc')}_"
        f"{main.get('StudyDescription','Desc')}"
    )


def get_series_display_name(series):
    tags = series.get("MainDicomTags", {})

    return safe_name(
        f"{tags.get('Modality','Mod')}_"
        f"Series_{tags.get('SeriesNumber','No')}_"
        f"{tags.get('SeriesDescription','Desc')}"
    )


# =========================
# UI
# =========================

st.set_page_config(page_title="Mini PACS Downloader", layout="wide")
st.title("Mini PACS Downloader + Preview Viewer 🩻")


# =========================
# SIDEBAR
# =========================

with st.sidebar:
    st.header("Settings")

    orthanc_url = st.text_input(
        "Orthanc URL",
        value=DEFAULT_ORTHANC_URL
    ).strip().rstrip("/")

    download_root = st.text_input(
        "Download folder",
        value=DEFAULT_DOWNLOAD_DIR
    )

    st.divider()

    st.header("Search")

    patient_id = st.text_input("Patient ID")
    patient_name = st.text_input("Patient Name")
    accession = st.text_input("Accession Number")
    study_date = st.text_input("Study Date YYYYMMDD")
    modality = st.text_input("Modality (CT/MR)")

    search_clicked = st.button("Search studies")


# =========================
# DEBUG CONNECTION
# =========================

st.write("🔗 Using Orthanc URL:", orthanc_url)

try:
    r = requests.get(f"{orthanc_url}/system", timeout=5)
    st.write("Status code:", r.status_code)
    st.write("Response:", r.text[:200])

    r.raise_for_status()
    system_info = r.json()

    st.success(f"Connected to Orthanc: {system_info.get('Name', 'Orthanc')}")

except Exception as e:
    st.error(f"Cannot connect to Orthanc at {orthanc_url}")
    st.exception(e)
    st.stop()


# =========================
# SEARCH
# =========================

if search_clicked:
    query = {}

    if patient_id:
        query["PatientID"] = patient_id
    if patient_name:
        query["PatientName"] = patient_name
    if accession:
        query["AccessionNumber"] = accession
    if study_date:
        query["StudyDate"] = study_date
    if modality:
        query["ModalitiesInStudy"] = modality

    payload = {
        "Level": "Study",
        "Query": query,
        "Expand": True
    }

    studies = orthanc_post(orthanc_url, "/tools/find", payload)
    st.session_state["studies"] = studies


# =========================
# DISPLAY
# =========================

studies = st.session_state.get("studies", [])

if studies:
    st.subheader(f"Found {len(studies)} studies")

    for study in studies:
        study_id = study["ID"]

        with st.expander(f"Study {study_id}"):

            study_folder = os.path.join(
                download_root,
                get_study_display_name(study)
            )

            st.code(study_folder)

            if st.button("Download study", key=study_id):
                download_archive(
                    orthanc_url,
                    "studies",
                    study_id,
                    study_folder
                )
                st.success("Downloaded ✔")

            if st.button("Load series", key=f"s_{study_id}"):
                data = orthanc_get(orthanc_url, f"/studies/{study_id}")
                st.session_state[f"series_{study_id}"] = data["Series"]

            series_ids = st.session_state.get(f"series_{study_id}", [])

            for series_id in series_ids:
                series = orthanc_get(orthanc_url, f"/series/{series_id}")

                st.write("Series:", series_id)

                if st.button("Preview", key=series_id):
                    inst = series["Instances"][0]
                    dcm = get_instance_file(orthanc_url, inst)
                    img = dicom_to_image(dcm)
                    st.image(img)

                if st.button("Download series", key=f"d_{series_id}"):
                    download_archive(
                        orthanc_url,
                        "series",
                        series_id,
                        os.path.join(study_folder, series_id)
                    )
                    st.success("Downloaded ✔")
