"""Seed IntelliDesk with starter Knowledge Base articles."""

from app import create_app, db
from app.models import Category, KnowledgeArticle, User


ARTICLES = [
    {
        "title": "Troubleshooting Wi-Fi and Network Connectivity",
        "summary": (
            "Diagnose common Wi-Fi disconnections, slow internet, "
            "and network connectivity problems."
        ),
        "category": "Network",
        "content": """
# Troubleshooting Wi-Fi and Network Connectivity

## Common symptoms

- Wi-Fi disconnects repeatedly.
- Websites fail to load.
- Internet access is slow or intermittent.
- A device cannot connect to the office network.

## Step 1: Check the connection

Confirm that Wi-Fi is enabled and that the device is connected to the
correct network. Check whether other devices experience the same problem.

## Step 2: Reconnect to the network

Disconnect from the Wi-Fi network and reconnect. If permitted by your
organization's policies, restart the device and test the connection again.

## Step 3: Check whether the problem affects one service or everything

Try opening an approved internal resource and a familiar website.
If only one service fails, the issue may be service-specific rather
than a general connectivity problem.

## Step 4: Check for a wider outage

If several devices are affected, check the organization's IT status
notifications or contact the network support team.

## Step 5: Escalate if necessary

Contact IT support if the connection continues to fail. Include the
device name, approximate time of the failure, network name, error
messages, and whether other users are affected.

Do not share Wi-Fi passwords or other credentials in a ticket.
""",
    },
    {
        "title": "Troubleshooting Windows Applications That Freeze or Crash",
        "summary": (
            "Resolve common application freezes, crashes, startup failures, "
            "and unexpected error messages."
        ),
        "category": "Software",
        "content": """
# Troubleshooting Windows Applications That Freeze or Crash

## Common symptoms

- An application stops responding.
- A program closes unexpectedly.
- An application fails to start.
- An error appears when opening a file or using a feature.

## Step 1: Record the error

Write down the application name, the action that caused the problem,
and the exact error message. Take a screenshot if permitted.

## Step 2: Retry the operation

Wait briefly to see whether the application recovers. If it remains
unresponsive, close it using normal operating-system controls.

Unsaved work may be lost when force-closing an application.

## Step 3: Restart the application and device

Reopen the application and repeat the operation. If the problem
continues, restart the device when practical.

## Step 4: Check for updates

Use the organization's approved software update process. Do not
download installers from unknown websites or bypass administrative
controls.

## Step 5: Check whether the issue is specific to one file

If the application works with other files, the original file may be
damaged or incompatible. Avoid deleting important files while testing.

## Step 6: Contact IT support

Provide the application name and version, operating system, error
message, steps to reproduce the problem, and whether it began after
a recent update.

Do not share confidential documents or authentication credentials
unless an approved support process specifically requires them.
""",
    },
    {
        "title": "Resolving Laptop and Desktop Hardware Problems",
        "summary": (
            "Perform basic checks for power problems, peripherals, "
            "overheating, and unresponsive computer hardware."
        ),
        "category": "Hardware",
        "content": """
# Resolving Laptop and Desktop Hardware Problems

## Common symptoms

- The computer does not power on.
- The display remains blank.
- A keyboard, mouse, or other peripheral stops working.
- The computer becomes unusually hot or shuts down unexpectedly.

## Step 1: Check power

For a desktop, confirm that the power cable is connected securely and
that the power outlet is working. For a laptop, check the charger and
charging indicator.

Do not open a power supply or damaged electrical equipment.

## Step 2: Check the display

Confirm that the monitor is powered on and that the correct input
source is selected. Check cable connections where safe and practical.

## Step 3: Test peripherals

Reconnect the affected peripheral if appropriate. If organizational
policy permits, test another approved port or known-working peripheral.

## Step 4: Check for overheating

Keep ventilation openings clear and place the computer on a suitable
surface. If the device is extremely hot, smells burnt, or makes unusual
electrical noises, stop using it and contact support.

## Step 5: Record the symptoms

Note any indicator lights, unusual sounds, error messages, and whether
the problem occurs during startup or normal operation.

## Step 6: Escalate

Contact IT support if basic checks do not resolve the problem.
Do not dismantle equipment or replace internal components unless
authorized and qualified to do so.
""",
    },
    {
        "title": "Troubleshooting Account Login and Password Issues",
        "summary": (
            "Resolve common sign-in failures, account lockouts, "
            "and password authentication problems."
        ),
        "category": "Account Access",
        "content": """
# Troubleshooting Account Login and Password Issues

## Common symptoms

- A password is rejected.
- An account is locked.
- Sign-in repeatedly returns to the login page.
- A service reports an authentication failure.

## Step 1: Verify the account identifier

Check that you are using the correct organizational username or email
address and that there are no accidental spaces or typing errors.

## Step 2: Check keyboard input

Confirm the keyboard layout and Caps Lock state. If the password field
has a visibility option, use it carefully and only when others cannot
see the screen.

## Step 3: Check the service

Confirm that you are using the correct sign-in page and that the service
is available. Avoid links received from unexpected messages.

## Step 4: Use the approved password recovery process

If the password is forgotten or expired, use your organization's
official password-reset procedure.

Do not repeatedly guess passwords, as this may lock the account.

## Step 5: Check multi-factor authentication

If the service requires an additional verification step, follow the
approved process. Never share one-time codes or approve unexpected
authentication requests.

## Step 6: Contact IT support

If access remains unavailable, report the service name, username
identifier if permitted, error message, and approximate time of failure.

Never include passwords, recovery codes, or one-time authentication
codes in a support ticket.
""",
    },
    {
        "title": "Resolving Email Sending and Receiving Problems",
        "summary": (
            "Troubleshoot email delivery failures, synchronization issues, "
            "and problems sending or receiving messages."
        ),
        "category": "Email & Communication",
        "content": """
# Resolving Email Sending and Receiving Problems

## Common symptoms

- Emails remain in the Outbox.
- New messages do not appear.
- Messages are returned as undeliverable.
- The email application repeatedly requests authentication.

## Step 1: Check connectivity

Confirm that the device has a working network connection and that
the email service is available.

## Step 2: Check the mailbox

Review the Outbox, Drafts, and Junk or Spam folders. Check whether
the mailbox has reached its storage limit.

## Step 3: Review delivery errors

If a message is returned, read the delivery status and error code.
A delivery failure may be caused by an invalid address, recipient
restrictions, or a receiving server problem.

## Step 4: Check synchronization

Refresh the mailbox and confirm that the application is connected
to the correct organizational account.

## Step 5: Follow approved update procedures

Install application updates only through approved channels. Do not
change server settings unless instructed by IT support.

## Step 6: Contact IT support

Provide the email application's name, the approximate time of failure,
the relevant error code, and whether sending, receiving, or both are
affected.

Do not include passwords or unnecessary confidential message content.
""",
    },
    {
        "title": "General IT Troubleshooting Guide",
        "summary": (
            "A safe first-response checklist for common computer, "
            "application, and service problems."
        ),
        "category": "Other",
        "content": """
# General IT Troubleshooting Guide

## Step 1: Describe the problem

Identify what is not working, what you expected to happen, and when
the problem started.

## Step 2: Identify the scope

Determine whether the problem affects one application, one device,
one account, or multiple users.

## Step 3: Record the error

Write down the exact error message and the steps that cause the issue.
Capture screenshots only when permitted by organizational policy.

## Step 4: Try safe basic checks

Check network connectivity, confirm cables are connected where
appropriate, and restart the affected application if safe.

Restart the device only when practical and when doing so will not
interrupt critical work or cause loss of unsaved data.

## Step 5: Avoid risky changes

Do not disable security software, bypass access controls, install
unapproved applications, delete important data, or share credentials.

## Step 6: Create a useful support ticket

Include:

- A concise title.
- A clear description.
- The affected application or device.
- The approximate start time.
- Relevant error messages.
- Troubleshooting steps already attempted.
- Whether other users are affected.

Remove passwords, access tokens, and unnecessary personal or
confidential information.

## Step 7: Follow up

Keep the ticket number for reference and add new diagnostic information
through the approved support process.
""",
    },
]


def main():
    app = create_app()

    with app.app_context():
        categories = {
            category.name: category
            for category in Category.query.filter_by(
                is_active=True
            ).all()
        }

        # Prefer an admin author for seeded documentation.
        author = (
            User.query.filter_by(
                role="admin",
                is_active=True,
            ).order_by(User.id).first()
        )

        if author is None:
            print(
                "No active admin account exists. "
                "Create or activate an admin account before seeding."
            )
            return

        created = 0
        skipped = 0

        for data in ARTICLES:
            existing = KnowledgeArticle.query.filter_by(
                title=data["title"]
            ).first()

            if existing:
                print(f"SKIPPED: {data['title']} (already exists)")
                skipped += 1
                continue

            category = categories.get(data["category"])

            if category is None:
                print(
                    f"SKIPPED: {data['title']} "
                    f"(active category '{data['category']}' not found)"
                )
                skipped += 1
                continue

            article = KnowledgeArticle(
                title=data["title"],
                slug="",  # Filled below using the project's slug utility.
                summary=data["summary"],
                content=data["content"].strip(),
                category_id=category.id,
                author_id=author.id,
                is_published=True,
            )

            # Import the existing slug generator instead of duplicating it.
            from app.routes.knowledge import generate_slug

            article.slug = generate_slug(data["title"])

            db.session.add(article)

            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                print(f"FAILED: {data['title']}")
                raise

            print(f"CREATED: {data['title']}")
            created += 1

        print("\nKnowledge Base seeding completed.")
        print(f"Created: {created}")
        print(f"Skipped: {skipped}")
        print(
            "Total published articles:",
            KnowledgeArticle.query.filter_by(
                is_published=True
            ).count(),
        )


if __name__ == "__main__":
    main()
