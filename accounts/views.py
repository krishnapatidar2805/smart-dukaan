from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from .utils import log_activity
from .models import Shop, Profile, AuditLog
from .forms import SignupForm, StaffCreateForm


def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = User.objects.create_user(
                username=data["username"],
                email=data.get("email", ""),
                password=data["password"],
                first_name=data["owner_name"],
            )
            shop = Shop.objects.create(name=data["shop_name"], owner=user)
            Profile.objects.create(user=user, shop=shop, role="owner", phone=data.get("phone", ""))
            login(request, user)
            log_activity(shop, user, "create", "accounts", f"Shop {shop.name}", f"Registered by {user.username}")
            messages.success(request, f"Welcome to Smart Dukaan, {data['owner_name']}!")
            return redirect("dashboard:home")
    else:
        form = SignupForm()
    return render(request, "accounts/signup.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            if hasattr(user, "profile") and user.profile.shop:
                log_activity(user.profile.shop, user, "create", "accounts", f"User Login", f"Logged in as {user.profile.role}")
            return redirect("dashboard:home")
        messages.error(request, "Invalid username or password.")
    return render(request, "accounts/login.html")


@login_required
def logout_view(request):
    if hasattr(request.user, "profile") and request.user.profile.shop:
        log_activity(request.user.profile.shop, request.user, "delete", "accounts", "User Logout", "Logged out")
    logout(request)
    return redirect("accounts:login")


@login_required
def add_staff_view(request):
    profile = request.user.profile
    if profile.role != "owner":
        messages.error(request, "Only the shop owner can manage staff.")
        return redirect("dashboard:home")

    if request.method == "POST":
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            if User.objects.filter(username=data["username"]).exists():
                messages.error(request, "Username already taken.")
            else:
                staff_user = User.objects.create_user(username=data["username"], password=data["password"])
                Profile.objects.create(user=staff_user, shop=profile.shop, role="staff", phone=data.get("phone", ""))
                log_activity(profile.shop, request.user, "create", "accounts", f"Staff {data['username']}", f"Phone: {data.get('phone', '')}")
                messages.success(request, f"Staff account '{data['username']}' created.")
                return redirect("accounts:staff_list")
    else:
        form = StaffCreateForm()
    staff = Profile.objects.filter(shop=profile.shop, role="staff")
    return render(request, "accounts/add_staff.html", {"form": form, "staff": staff})


@login_required
def audit_log_view(request):
    profile = request.user.profile
    if profile.role != "owner":
        messages.error(request, "Only the shop owner can access the Audit Trail & Activity Log.")
        return redirect("dashboard:home")

    logs = AuditLog.objects.filter(shop=profile.shop)

    module_filter = request.GET.get("module", "")
    action_filter = request.GET.get("action", "")
    user_filter = request.GET.get("user", "")
    query = request.GET.get("q", "")

    if module_filter:
        logs = logs.filter(module=module_filter)
    if action_filter:
        logs = logs.filter(action=action_filter)
    if user_filter:
        logs = logs.filter(user__username=user_filter)
    if query:
        logs = logs.filter(Q(object_repr__icontains=query) | Q(details__icontains=query))

    paginator = Paginator(logs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    staff_users = Profile.objects.filter(shop=profile.shop).select_related("user")

    return render(request, "accounts/audit_log.html", {
        "logs": page_obj,
        "page_obj": page_obj,
        "module_filter": module_filter,
        "action_filter": action_filter,
        "user_filter": user_filter,
        "query": query,
        "staff_users": staff_users,
        "modules": AuditLog.MODULE_CHOICES,
        "actions": AuditLog.ACTION_CHOICES,
    })


@login_required
def audit_log_clear(request):
    profile = request.user.profile
    if profile.role != "owner":
        messages.error(request, "Only the shop owner can clear activity logs.")
        return redirect("dashboard:home")
    if request.method == "POST":
        count = AuditLog.objects.filter(shop=profile.shop).count()
        AuditLog.objects.filter(shop=profile.shop).delete()
        messages.success(request, f"Permanently deleted {count} activity log entries.")
    return redirect("accounts:audit_log")

