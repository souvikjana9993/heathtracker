import streamlit as st
import streamlit_authenticator as stauth
from streamlit_authenticator.utilities import LoginError
import yaml
from yaml.loader import SafeLoader

with open("./config.yaml") as file:
    auth_config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    auth_config["credentials"],
    auth_config["cookie"]["name"],
    auth_config["cookie"]["key"],
    auth_config["cookie"]["expiry_days"],
)

try:
    authenticator.login("main")
except LoginError as e:
    st.error(e)

if st.session_state["authentication_status"]:
      st.write(f"Welcome *{st.session_state['name']}*")
      authenticator.logout("Logout")

elif st.session_state["authentication_status"] is False:
    st.error("Username/password is incorrect")
elif st.session_state["authentication_status"] is None:
    st.warning("Please enter your username and password")