import streamlit as st
import yaml
from yaml.loader import SafeLoader
from streamlit_authenticator import Authenticate

# Load configuration
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

# Initialize authenticator
authenticator = Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

# Login widget
name, authentication_status, username = authenticator.login('Login', 'main')

# Handle authentication response
if authentication_status:
    st.success(f"Welcome *{name}*!")
    authenticator.logout('Logout', 'sidebar')
elif authentication_status is False:
    st.error("Username/password is incorrect")
elif authentication_status is None:
    st.warning("Enter your username and password")