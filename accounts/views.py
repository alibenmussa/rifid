from django.contrib.auth import authenticate, logout, login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.contrib import messages
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.safestring import mark_safe


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        print(username, password)
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "اسم المستخدم أو كلمة المرور غير صحيحة")
    return render(request, "auth-login.html")


@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'تم تسجيل الخروج بنجاح')
    return redirect('home')
