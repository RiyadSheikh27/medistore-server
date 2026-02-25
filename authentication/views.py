from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import *
from .serializers import *
from .otp_utils import get_tokens_for_user
from .email_utils import send_otp_email
from .permissions import IsAdmin
import random
import logging

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([AllowAny])
def registration(request):
    """Register user and send OTP"""
    serializer = RegistrationSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    otp = str(random.randint(100000, 999999))

    try:
        send_otp_email(
            subject='Email Verification - OTP',
            template_name='emails/registration_otp.html',
            context={'otp': otp},
            recipient_email=email,
        )

        """Save to pending table only — no user created yet"""
        PendingRegistration.objects.update_or_create(
            email=email,
            defaults={
                'first_name': serializer.validated_data.get('first_name', ''),
                'last_name': serializer.validated_data.get('last_name', ''),
                'password': serializer.validated_data['password'],
                'phone': serializer.validated_data.get('phone', None),
                'address': serializer.validated_data.get('address', None),
                'image': serializer.validated_data.get('image', None),
                'otp': otp,
                'otp_expires_at': timezone.now() + timezone.timedelta(minutes=5),
            }
        )

        print(otp)

        return Response({
            'success': True,
            'message': f'OTP sent to {email}',
            'email': email
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Registration error for %s: %s", email, str(e))
        return Response({
            'success': False,
            'message': 'Failed to send OTP. Please try again.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def resend_otp(request):
    """Resend OTP for both registration and password reset"""
    email = request.data.get('email')
    if not email:
        return Response({
            'success': False,
            'message': 'Email is required.'
        }, status=status.HTTP_400_BAD_REQUEST)

    otp = str(random.randint(100000, 999999))

    try:
        """Check registration pending first"""
        try:
            pending = PendingRegistration.objects.get(email=email)

            send_otp_email(
                subject='Email Verification - OTP',
                template_name='emails/registration_otp.html',
                context={'otp': otp},
                recipient_email=email,
            )

            pending.otp = otp
            pending.otp_expires_at = timezone.now() + timezone.timedelta(minutes=5)
            pending.save(update_fields=['otp', 'otp_expires_at'])

            print(otp)

            return Response({
                'success': True,
                'message': f'OTP resent to {email}',
                'email': email
            }, status=status.HTTP_200_OK)

        except PendingRegistration.DoesNotExist:
            pass

        """Check password reset"""
        try:
            user = Users.objects.get(email=email)

            send_otp_email(
                subject='Password Reset - OTP',
                template_name='emails/password_reset_otp.html',
                context={'otp': otp},
                recipient_email=email,
            )

            user.otp = otp
            user.save(update_fields=['otp', 'otp_expired'])

            print(otp)

            return Response({
                'success': True,
                'message': f'OTP resent to {email}',
                'email': email
            }, status=status.HTTP_200_OK)

        except Users.DoesNotExist:
            return Response({
                'success': False,
                'message': 'No account or pending registration found for this email.'
            }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error("Resend OTP error for %s: %s", email, str(e))
        return Response({
            'success': False,
            'message': 'Failed to resend OTP. Please try again.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_registration_otp(request):
    """Verify OTP for both registration and password reset"""
    serializer = VerifyOTPSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    otp = serializer.validated_data['otp']

    """Registration flow """
    try:
        pending = PendingRegistration.objects.get(email=email)

        if pending.otp != otp:
            return Response({
                'success': False,
                'message': 'Invalid OTP.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if timezone.now() > pending.otp_expires_at:
            pending.delete()
            return Response({
                'success': False,
                'message': 'OTP has expired. Please register again.'
            }, status=status.HTTP_400_BAD_REQUEST)

        """OTP verified — now create the real user"""
        user = Users.objects.create(
            email=pending.email,
            first_name=pending.first_name,
            last_name=pending.last_name,
            phone=pending.phone,
            address=pending.address,
            image=pending.image or None,
            is_active=True,
        )
        user.set_password(pending.password)
        user.save()

        pending.delete()

        tokens = get_tokens_for_user(user)
        return Response({
            'success': True,
            'message': 'Registration completed successfully',
            'user': UserProfileSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_201_CREATED)

    except PendingRegistration.DoesNotExist:
        pass  # not a registration — fall through to password reset check

    except Exception as e:
        logger.error("User creation failed for %s: %s", email, str(e))
        return Response({
            'success': False,
            'message': 'Failed to create user. Please try again.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    """Password reset flow"""
    try:
        user = Users.objects.get(email=email)

        if user.otp != otp:
            return Response({
                'success': False,
                'message': 'Invalid OTP.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not user.otp_expired or timezone.now() > user.otp_expired:
            return Response({
                'success': False,
                'message': 'OTP has expired. Please request a new one.'
            }, status=status.HTTP_400_BAD_REQUEST)

        user.otp = None
        user.otp_expired = None
        user.save(update_fields=['otp', 'otp_expired'])

        return Response({
            'success': True,
            'message': 'OTP verified successfully. Please set your new password.',
            'email': email
        }, status=status.HTTP_200_OK)

    except Users.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Invalid or expired OTP.'
        }, status=status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        logger.error("OTP verify error for %s: %s", email, str(e))
        return Response({
            'success': False,
            'message': 'OTP verification failed. Please try again.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Login user"""
    serializer = LoginSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = serializer.validated_data['user']
        tokens = get_tokens_for_user(user)

        return Response({
            'success': True,
            'message': 'Login successful',
            'user': UserProfileSerializer(user).data,
            'tokens': tokens
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Login error: %s", str(e))
        return Response({
            'success': False,
            'message': 'Login failed. Please try again.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """Send OTP for password reset"""
    serializer = ForgotPasswordSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    otp = str(random.randint(100000, 999999))

    try:
        send_otp_email(
            subject='Password Reset - OTP',
            template_name='emails/password_reset_otp.html',
            context={'otp': otp},
            recipient_email=email,
        )

        user = Users.objects.get(email=email)
        user.otp = otp
        # model's save() auto-sets otp_expired to now + 5 minutes
        user.save(update_fields=['otp', 'otp_expired'])

        print(otp)

        return Response({
            'success': True,
            'message': f'OTP sent to {email}',
            'email': email
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Forgot password error for %s: %s", email, str(e))
        return Response({
            'success': False,
            'message': f'Failed to send OTP. Please try again.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """Reset password after OTP verification"""
    serializer = ResetPasswordSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    new_password = serializer.validated_data['new_password']

    try:
        user = Users.objects.get(email=email)

        # otp=None means verify_otp was called successfully
        if user.otp is not None:
            return Response({
                'success': False,
                'message': 'Please verify OTP first.'
            }, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({
            'success': True,
            'message': 'Password reset successfully'
        }, status=status.HTTP_200_OK)

    except Users.DoesNotExist:
        return Response({
            'success': False,
            'message': 'User not found.'
        }, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        logger.error("Reset password error for %s: %s", email, str(e))
        return Response({
            'success': False,
            'message': 'Failed to reset password. Please try again.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change password for authenticated user"""
    serializer = ChangePasswordSerializer(data=request.data, context={'request': request})

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({
            'success': True,
            'message': 'Password changed successfully'
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Change password error for %s: %s", request.user.email, str(e))
        return Response({
            'success': False,
            'message': 'Failed to change password. Please try again.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_profile(request):
    """Get user profile"""
    try:
        serializer = UserProfileSerializer(request.user)
        return Response({
            'success': True,
            'user': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Get profile error: %s", str(e))
        return Response({
            'success': False,
            'message': 'Failed to fetch profile.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """Update user profile"""
    serializer = UpdateProfileSerializer(
        request.user,
        data=request.data,
        partial=True
    )

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        serializer.save()
        return Response({
            'success': True,
            'message': 'Profile updated successfully',
            'user': UserProfileSerializer(request.user).data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Update profile error for %s: %s", request.user.email, str(e))
        return Response({
            'success': False,
            'message': 'Failed to update profile.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAdmin])
def user_list(request):
    """Get all users (Admin only)"""
    try:
        users = Users.objects.all().order_by('-created_at')

        serializer = UserListSerializer(users, many=True)

        return Response({
            'success': True,
            'message': 'Users retrieved successfully',
            'statistics': {
                'total_users': users.count(),
                'total_active_users': users.filter(is_active=True).count(),
                'total_inactive_users': users.filter(is_active=False).count(),
            },
            'users': serializer.data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("User list error: %s", str(e))
        return Response({
            'success': False,
            'message': 'Failed to retrieve users.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT'])
@permission_classes([IsAdmin])
def ChangeUserStatus(request, user_id):
    """Update user Status"""
    try:
        user = get_object_or_404(Users, id=user_id)
        serializer = UserStatusChangeSerializer(user, data=request.data)

        if not serializer.is_valid():
            return Response({
                'success': False,
                'errors': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response({
            'success': True,
            'message': 'User status changed successfully',
            'user': UserStatusChangeSerializer(user).data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error("Change user status error (user_id=%s): %s", user_id, str(e))
        return Response({
            'success': False,
            'message': 'Failed to update user status.',
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)