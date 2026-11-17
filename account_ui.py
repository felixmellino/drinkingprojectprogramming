"""The account screen shared by the first visit and Profile page."""

import streamlit as st
from postgrest.exceptions import APIError
from httpx import RequestError

import data.db as db
from core.auth import authenticate
from core.lobbies import create_player
from device_login import finish_login

def show_error(error):
    if isinstance(error, ValueError):
        st.error(str(error))
    elif isinstance(error, APIError) and error.code == "23505":
        st.error("That username or email is already registered.")
    else:
        st.error("Account service is unavailable. Please try again later.")


def show_accounts():
    st.title("Profile")
    st.caption("Create an account to play, or log in if you already have one.")
    action = st.radio("Choose an action", ["Create account", "Log in"], horizontal=True, key="account_action")
    if action == "Create account":
        st.caption("Only your username is public. Your name and email stay private.")
        with st.form("create_account"):
            first = st.text_input("First name")
            last = st.text_input("Surname")
            username = st.text_input("Username")
            email = st.text_input("Email")
            password = st.text_input("Password", type="password", help="At least 8 characters")
            confirmation = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account")
        if submitted:
            try:
                player = create_player(username, first, last, email, password, confirmation, db.list_players())
                db.insert_player(player)
                finish_login(player)
            except (ValueError, APIError, RuntimeError, OSError, RequestError) as exc:
                show_error(exc)

    else:
        with st.form("login"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            remember = st.checkbox("Remember password", help="Keep me signed in on this device for 30 days.")
            submitted = st.form_submit_button("Log in")
        if submitted:
            try:
                players = db.list_players()
                candidate = next((p for p in players if p.email and p.email == email.strip().lower()), None)
                if candidate and not db.allow_login_attempt(candidate.id):
                    raise ValueError("Too many login attempts. Try again in 15 minutes.")
                player = authenticate(email, password, players)
                if player:
                    finish_login(player, remember)
                else:
                    st.error("Email or password is incorrect.")
            except (ValueError, APIError, RuntimeError, OSError, RequestError) as exc:
                show_error(exc)
