from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from functools import cache
import logging
import os
import smtplib
from typing import Iterable
from pathlib import Path
from ms_active_directory import ADDomain, ADUser
from ldap3 import SASL, GSSAPI

logger = logging.getLogger(__name__)
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from pykeepass import Entry, PyKeePass


class KeepassConnector(BaseSettings, env_prefix="ALLENINST_KEEPASS_"):
    db: Path
    keyfile: Path

    def get_credentials(
        self,
        entry_title: str,
        fields_to_return: Iterable[str] = ("username", "password"),
    ) -> dict[str, str]:

        keepass = PyKeePass(self.db, keyfile=self.keyfile)
        entries = keepass.find_entries(title=entry_title)
        if len(entries) == 0:
            logger.warning(f"Entry {entry_title} not found in Keepass database")
            return
        else:
            entry: Entry = entries[0]
            return_fields = {}
            for field in fields_to_return:
                if hasattr(entry, field):
                    return_fields[field] = entry.__getattribute__(field)
                elif field in entry.custom_properties:
                    return_fields[field] = entry.custom_properties.get(field)
            return return_fields


class UserCredentials(BaseSettings):
    username: str
    password: SecretStr

    @classmethod
    def from_keepass(cls, keepass_entry_title: str):
        return cls(**KeepassConnector().get_credentials(keepass_entry_title, ["username", "password"]))


user_creds_to_query_with: UserCredentials = None


@cache
def get_user_from_active_directory(username: str) -> tuple[str, str, str]:
    """Queries active directory for user information

    Params:
        username (str): user login or full name

    Returns:
        username (str): samaccount_name of the user
        full_name (str): common name of the user
        email (str): email address of the user
    """
    global user_creds_to_query_with
    if user_creds_to_query_with is None:
        try:
            user_creds_to_query_with = UserCredentials.from_keepass("svc_mpe")
        except:
            logger.exception("Could not find svc_mpe credentials")

    domain = ADDomain("corp.alleninstitute.org")
    session = domain.create_session_as_user(
        user_creds_to_query_with.username,
        user_creds_to_query_with.password.get_secret_value(),
    )
    ad_user = session.find_user_by_name(username, attributes_to_lookup=["mail"])
    if ad_user is None:
        raise ValueError(f"User {username} not found in the institute Active Directory")
    return ad_user.samaccount_name, ad_user.common_name, ad_user.all_attributes["mail"]


def send_email(
    subject: str,
    body: str,
    to: list[str],
) -> None:
    """
    Compile subject and body into an email, and send using the computer's SMTP server.
    """

    msg = MIMEMultipart("alternative")
    # Attach the HTML body
    html_part = MIMEText(body, "html", "utf-8")
    msg.attach(html_part)

    msg["Subject"] = subject
    msg["From"] = "svc_mpe@alleninstitute.org"
    msg["To"] = ", ".join(to)

    smtp_server =  "aidc-mx-1.corp.alleninstitute.org"

    # Send message
    try:
        
        with smtplib.SMTP(smtp_server) as s:
            s.send_message(msg)
            print(f"EMAILING {to}")
        logger.info(
            f"Sent email",
            subject=subject,
            to=to,
            body=body,
        )
    except:
        logger.exception(
            "Failed to send email",
            subject=subject,
            to=to,
            body=body,
        )

if __name__ == "__main__":
    header = f'<h2>Error occured durring run:</h2>'
    msg = f'<h3>Device error. Please check device.</h3>'
    send_email(subject="Test Email", body=header + msg, to=["micah.woodard@alleninstitute.org"])