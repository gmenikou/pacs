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

DEFAULT_ORTHANC_URL = "http://localhost:8042"
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


def dicom_to_image(dicom_bytes, window_center=None, window_width=None):
    ds = pydicom.dcmread(BytesIO(dicom_bytes))
    arr = ds.pixel_array.astype(np.float32)

    slope = float(getattr(ds, "RescaleSlope", 1))
    intercept = float(getattr(ds, "RescaleIntercept", 0))
    arr = arr * slope + intercept

    if window_center is None:
        wc = getattr(ds, "WindowCenter", None)
        if isinstance(wc, pydicom.multival.MultiValue):
            wc = wc[0]
        window_center = float(wc) if wc is not None else None

    if window_width is None:
        ww = getattr(ds, "WindowWidth", None)
        if isinstance(ww, pydicom.multival.MultiValue):
            ww = ww[0]
        window_width = float(ww) if ww is not None else None

    if window_center is not None and window_width is not None:
        low = window_center - window_width / 2
        high = window_center + window_width / 2
        arr = np.clip(arr, low, high)

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

    patient_name = patient.get("PatientName", "UnknownPatient")
    patient_id = patient.get("PatientID", "UnknownID")
    study_date = main.get("StudyDate", "UnknownDate")
    accession = main.get("AccessionNumber", "NoAccession")
    description = main.get("StudyDescription", "NoDescription")

    return safe_name(f"{patient_id}_{patient_name}_{study_date}_{accession}_{description}")


def get_series_display_name(series):
    tags = series.get("MainDicomTags", {})

    modality = tags.get("Modality", "UnknownModality")
    number = tags.get("SeriesNumber", "NoSeriesNumber")
    description = tags.get("SeriesDescription", "NoDescription")

    return safe_name(f"{modality}_Series_{number}_{description}")


# =========================
# STREAMLIT UI
# =========================

st.set_page_config(
    page_title="Mini PACS Downloader",
    layout="wide"
)

st.title("Mini PACS Downloader + Preview Viewer 🩻")

with st.sidebar:
    st.header("Settings")

    orthanc_url = st.text_input(
        "Orthanc URL",
        value=DEFAULT_ORTHANC_URL
    ).rstrip("/")

    download_root = st.text_input(
        "Download folder",
        value=DEFAULT_DOWNLOAD_DIR
    )

    st.caption("Example: `/home/user/dicom_downloads` or `D:/DICOM_Downloads`")

    st.divider()

    st.header("Search")

    patient_id = st.text_input("Patient ID")
    patient_name = st.text_input("Patient Name")
    accession = st.text_input("Accession Number")
    study_date = st.text_input("Study Date YYYYMMDD")
    modality = st.text_input("Modality, e.g. CT or MR")

    search_clicked = st.button("Search studies")


# =========================
# TEST CONNECTION
# =========================

try:
    system_info = orthanc_get(orthanc_url, "/system")
    st.success(f"Connected to Orthanc: {system_info.get('Name', 'Orthanc')}")
except Exception as e:
    st.error(f"Cannot connect to Orthanc at {orthanc_url}")
    st.stop()


# =========================
# SEARCH STUDIES
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

    try:
        studies = orthanc_post(orthanc_url, "/tools/find", payload)
        st.session_state["studies"] = studies
    except Exception as e:
        st.error(f"Search failed: {e}")


# =========================
# DISPLAY STUDIES
# =========================

studies = st.session_state.get("studies", [])

if studies:
    st.subheader(f"Found {len(studies)} studies")

    for idx, study in enumerate(studies):
        study_id = study["ID"]
        study_tags = study.get("MainDicomTags", {})
        patient_tags = study.get("PatientMainDicomTags", {})

        patient_id_value = patient_tags.get("PatientID", "")
        patient_name_value = patient_tags.get("PatientName", "")
        study_date_value = study_tags.get("StudyDate", "")
        accession_value = study_tags.get("AccessionNumber", "")
        description_value = study_tags.get("StudyDescription", "")

        with st.expander(
            f"{idx + 1}. {patient_id_value} | {patient_name_value} | "
            f"{study_date_value} | {accession_value} | {description_value}"
        ):
            col_a, col_b, col_c = st.columns([2, 2, 2])

            with col_a:
                st.write("**Patient ID:**", patient_id_value)
                st.write("**Patient Name:**", patient_name_value)

            with col_b:
                st.write("**Study Date:**", study_date_value)
                st.write("**Accession:**", accession_value)

            with col_c:
                st.write("**Description:**", description_value)
                st.write("**Orthanc Study ID:**", study_id)

            study_folder_name = get_study_display_name(study)
            study_destination = os.path.join(download_root, study_folder_name)

            st.code(study_destination)

            if st.button("Download full study", key=f"download_study_{study_id}"):
                try:
                    saved_to = download_archive(
                        orthanc_url,
                        "studies",
                        study_id,
                        study_destination
                    )
                    st.success(f"Study saved to: {saved_to}")
                except Exception as e:
                    st.error(f"Study download failed: {e}")

            if st.button("Load series", key=f"load_series_{study_id}"):
                full_study = orthanc_get(orthanc_url, f"/studies/{study_id}")
                st.session_state[f"series_{study_id}"] = full_study.get("Series", [])

            series_ids = st.session_state.get(f"series_{study_id}", [])

            if series_ids:
                st.markdown("### Series")

                for series_id in series_ids:
                    try:
                        series = orthanc_get(orthanc_url, f"/series/{series_id}")
                    except Exception:
                        continue

                    series_tags = series.get("MainDicomTags", {})
                    series_name = get_series_display_name(series)
                    series_destination = os.path.join(study_destination, series_name)

                    st.markdown("---")
                    st.write(
                        f"**{series_tags.get('Modality', '')} | "
                        f"Series {series_tags.get('SeriesNumber', '')} | "
                        f"{series_tags.get('SeriesDescription', '')}**"
                    )

                    st.code(series_destination)

                    col1, col2, col3 = st.columns([1, 1, 2])

                    with col1:
                        if st.button("Preview", key=f"preview_{series_id}"):
                            instances = series.get("Instances", [])

                            if not instances:
                                st.warning("No instances found in this series.")
                            else:
                                st.session_state[f"preview_series_{series_id}"] = instances

                    with col2:
                        if st.button("Download series", key=f"download_series_{series_id}"):
                            try:
                                saved_to = download_archive(
                                    orthanc_url,
                                    "series",
                                    series_id,
                                    series_destination
                                )
                                st.success(f"Series saved to: {saved_to}")
                            except Exception as e:
                                st.error(f"Series download failed: {e}")

                    preview_instances = st.session_state.get(f"preview_series_{series_id}")

                    if preview_instances:
                        slice_index = st.slider(
                            "Slice",
                            min_value=0,
                            max_value=len(preview_instances) - 1,
                            value=0,
                            key=f"slice_{series_id}"
                        )

                        instance_id = preview_instances[slice_index]

                        try:
                            dicom_bytes = get_instance_file(orthanc_url, instance_id)
                            img = dicom_to_image(dicom_bytes)

                            with col3:
                                st.image(
                                    img,
                                    caption=f"Preview slice {slice_index + 1}/{len(preview_instances)}",
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.error(f"Preview failed: {e}")

else:
    st.info("Search for a study using the sidebar.")
