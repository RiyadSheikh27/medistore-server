from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import Users
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
    """Step 1: Register user and send OTP"""
    serializer = RegistrationSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    otp = str(random.randint(1000, 9999))

    try:
        send_otp_email(
            subject='Email Verification - OTP',
            template_name='emails/registration_otp.html',
            context={'otp': otp},
            recipient_email=email,
        )

        user, created = Users.objects.get_or_create(
            email=email,
            defaults={
                'first_name': serializer.validated_data.get('first_name', ''),
                'last_name': serializer.validated_data.get('last_name', ''),
                'is_active': False,
            }
        )
        if not created:
            user.first_name = serializer.validated_data.get('first_name', '')
            user.last_name = serializer.validated_data.get('last_name', '')

        if serializer.validated_data.get('image'):
            user.image = serializer.validated_data['image']

        user.set_password(serializer.validated_data['password'])
        user.otp = otp
        user.save()

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
def verify_registration_otp(request):
    """Step 2: Verify OTP for both registration and password reset"""
    serializer = VerifyOTPSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    otp = serializer.validated_data['otp']

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

        # Clear OTP
        user.otp = None
        user.otp_expired = None

        # Registration flow — user is inactive
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=['otp', 'otp_expired', 'is_active'])

            tokens = get_tokens_for_user(user)
            return Response({
                'success': True,
                'message': 'Registration completed successfully',
                'user': UserProfileSerializer(user).data,
                'tokens': tokens
            }, status=status.HTTP_201_CREATED)

        # Password reset flow — user is already active
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
    otp = str(random.randint(1000, 9999))

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