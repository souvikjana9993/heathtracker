from streamlit_authenticator import Hasher

# Hash a password
hashed_password = Hasher(['123']).generate()[0]  # Replace '123' with your password
print(f"Hashed password: {hashed_password}")