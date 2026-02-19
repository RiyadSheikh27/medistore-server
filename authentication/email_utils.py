from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings


def send_otp_email(subject: str, template_name: str, context: dict, recipient_email: str) -> None:
    """
    Send an HTML OTP email using a template file.
    """
    # Convert OTP string to a list of individual digits for the template
    otp_str = context.get('otp', '')
    context['otp'] = list(otp_str)

    html_message = render_to_string(template_name, context)

    # Plain-text fallback
    text_message = (
        f"Your OTP is: {otp_str}\n\n"
        "This OTP is valid for 5 minutes. Do not share this code with anyone."
    )

    email_msg = EmailMultiAlternatives(
        subject=subject,
        body=text_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )
    email_msg.attach_alternative(html_message, "text/html")
    email_msg.send(fail_silently=False)