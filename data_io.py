import io
import os

import pandas as pd

SUPPORTED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}


def attachment_extension(filename):
    return os.path.splitext(filename.lower())[1]


def is_supported_attachment(filename):
    return attachment_extension(filename) in SUPPORTED_EXTENSIONS


def load_dataframe_from_bytes(content, filename):
    ext = attachment_extension(filename)
    if ext == '.csv':
        return pd.read_csv(io.BytesIO(content))
    if ext == '.xlsx':
        return pd.read_excel(io.BytesIO(content), engine='openpyxl')
    if ext == '.xls':
        return pd.read_excel(io.BytesIO(content), engine='xlrd')
    raise ValueError(f'Unsupported file type: {filename}')


def load_dataframe_from_path(path):
    with open(path, 'rb') as handle:
        return load_dataframe_from_bytes(handle.read(), os.path.basename(path))
