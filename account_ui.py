"""The account screen shared by the first visit and Profile page."""

import logging

import streamlit as st
from postgrest.exceptions import APIError
from httpx import RequestError

import data.db as db
from data.mail import MailUnavailable, mail_settings, send_reset_code
from core.auth import (authenticate, hash_password, new_reset_code, normalize_email,
                       reset_code_hash, validate_password)
from core.lobbies import create_player
from device_login import finish_login

logger = logging.getLogger(__name__)


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

        with st.expander("Forgot password?"):
            st.caption("Request a code by email, then enter it below. Codes expire after 15 minutes.")
            with st.form("request_reset"):
                email = st.text_input("Email", key="recovery_email")
                submitted = st.form_submit_button("Send reset code")
            if submitted:
                try:
                    email = normalize_email(email)
                    settings = mail_settings()
                    player = next((p for p in db.list_players() if p.email == email), None)
                    if player:
                        code, code_hash = new_reset_code()
                        if db.issue_password_reset(player.id, code_hash):
                            try:
                                send_reset_code(email, code, settings)
                            except MailUnavailable:
                                # Keep the same response for registered and unknown addresses.
                                logger.warning("Password recovery email delivery failed")
                    st.success("If that email is registered, a reset code has been requested. Check your inbox and spam folder. Wait a minute before requesting another.")
                except MailUnavailable as exc:
                    st.error(str(exc))
                except (ValueError, APIError, RuntimeError, OSError, RequestError) as exc:
                    show_error(exc)
            with st.form("reset_password"):
                email = st.text_input("Account email")
                code = st.text_input("Reset code", type="password")
                password = st.text_input("New password", type="password")
                confirmation = st.text_input("Confirm new password", type="password")
                submitted = st.form_submit_button("Save new password")
            if submitted:
                try:
                    email = normalize_email(email)
                    validate_password(password, confirmation)
                    if not code.strip() or not db.consume_password_reset(email, reset_code_hash(code), hash_password(password)):
                        st.error("Reset code is invalid or expired. Request a new one.")
                    else:
                        st.success("Password updated. Log in with your new password.")
                except (ValueError, APIError, RuntimeError, OSError, RequestError) as exc:
                    show_error(exc)

