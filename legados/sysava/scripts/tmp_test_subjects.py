import os
import sys
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.abspath('b:\\Dev\\SysAva\\scripts\\seed_simulado.py'))
sys.path.append(project_root)
load_dotenv(dotenv_path=os.path.join(project_root, '.env'))

import streamlit as st
class MockSecrets(dict):
    def __getitem__(self, key):
        return os.environ.get(key)
st.secrets = MockSecrets()

from legados.sysava.services import database as db
subjects = db.get_subjects()
for s in subjects:
    print(f"ID: {s['id']}, Nome: {s['name']}")
