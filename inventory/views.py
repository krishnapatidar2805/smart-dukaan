import os
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from billing.models import BillItem
from accounts.utils import log_activity
from .models import Product
from .forms import ProductForm


@login_required
def product_list(request):
    shop = request.user.profile.shop
    products = Product.objects.filter(shop=shop)
    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(category__icontains=query))
    category = request.GET.get("category", "").strip()
    if category:
        products = products.filter(category=category)

    stock_filter = request.GET.get("stock_filter", "")

    # Calculate 30-Day Restock Predictions for each product
    thirty_days_ago = timezone.now() - timedelta(days=30)
    sales_30d = (
        BillItem.objects.filter(bill__shop=shop, bill__date__gte=thirty_days_ago)
        .values("product_id")
        .annotate(total_sold=Sum("quantity"))
    )
    sales_map = {item["product_id"]: item["total_sold"] for item in sales_30d}

    product_list_data = []
    critical_reorder_count = 0

    for p in products:
        sold_30d = sales_map.get(p.id, 0)
        daily_rate = sold_30d / 30.0 if sold_30d > 0 else 0.0

        if daily_rate > 0:
            days_left = round(p.stock_qty / daily_rate, 1)
        else:
            days_left = None

        reorder_soon = (days_left is not None and days_left <= 5) or p.is_low_stock
        if reorder_soon:
            critical_reorder_count += 1

        p.daily_rate = round(daily_rate, 2)
        p.sold_30d = sold_30d
        p.days_left = days_left
        p.reorder_soon = reorder_soon
        product_list_data.append(p)

    if stock_filter == "reorder":
        product_list_data = [p for p in product_list_data if p.reorder_soon]
    elif stock_filter == "low":
        product_list_data = [p for p in product_list_data if p.is_low_stock]

    paginator = Paginator(product_list_data, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    categories = Product.objects.filter(shop=shop).values_list("category", flat=True).distinct()

    return render(request, "inventory/product_list.html", {
        "products": page_obj,
        "page_obj": page_obj,
        "query": query,
        "categories": categories,
        "selected_category": category,
        "stock_filter": stock_filter,
        "critical_reorder_count": critical_reorder_count,
        "total_products": len(product_list_data),
    })


@login_required
def product_add(request):
    shop = request.user.profile.shop
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            product = form.save(commit=False)
            product.shop = shop
            product.save()
            log_activity(
                shop, request.user, "create", "inventory",
                f"Product {product.name}",
                f"Stock: {product.stock_qty} {product.unit}, Selling Price: Rs. {product.selling_price}, Cost: Rs. {product.cost_price}"
            )
            messages.success(request, f"Product '{product.name}' added successfully.")
            return redirect("inventory:product_list")
    else:
        form = ProductForm()
    return render(request, "inventory/product_form.html", {"form": form, "title": "Add Product"})


@login_required
def product_edit(request, pk):
    shop = request.user.profile.shop
    product = get_object_or_404(Product, pk=pk, shop=shop)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            log_activity(
                shop, request.user, "update", "inventory",
                f"Product {product.name}",
                f"Updated stock: {product.stock_qty}, Price: Rs. {product.selling_price}"
            )
            messages.success(request, f"Product '{product.name}' updated successfully.")
            return redirect("inventory:product_list")
    else:
        form = ProductForm(instance=product)
    return render(request, "inventory/product_form.html", {"form": form, "title": f"Edit {product.name}"})


@login_required
def product_delete(request, pk):
    shop = request.user.profile.shop
    product = get_object_or_404(Product, pk=pk, shop=shop)
    name = product.name
    product.delete()
    log_activity(shop, request.user, "delete", "inventory", f"Product {name}", "Deleted product")
    messages.success(request, f"Product '{name}' deleted.")
    return redirect("inventory:product_list")


@login_required
def suggest_category_api(request):
    """Suggest category based on product name via keyword heuristics + Anthropic API fallback."""
    name = request.GET.get("name", "").strip().lower()
    if not name:
        return JsonResponse({"category": ""})

    # Keyword Taxonomy Dictionary for Kirana / General / Medical / Cosmetics
    TAXONOMY = {
        "Grocery & Staples": [
            "atta", "flour", "rice", "chawal", "basmati", "dal", "moong", "urad", "chana",
            "oil", "tel", "refined", "mustard", "sarson", "ghee", "sugar", "cheeni", "salt",
            "namak", "besan", "maida", "sooji", "suji", "poha", "masala", "spice", "haldi",
            "mirch", "chilli", "jeera", "dhaniya", "garam masala", "hing", "grain", "wheat"
        ],
        "Snacks & Beverages": [
            "tea", "chai", "coffee", "biscuit", "cookie", "rusk", "chips", "kurkure", "lays",
            "chocolate", "cadbury", "kitkat", "candy", "maggi", "noodle", "pasta", "sauce",
            "ketchup", "jam", "cold drink", "coke", "pepsi", "sprite", "juice", "frooti",
            "namkeen", "bhujia", "wafers", "snack"
        ],
        "Personal Care & Cosmetics": [
            "soap", "sabun", "shampoo", "conditioner", "paste", "toothpaste", "colgate",
            "brush", "toothbrush", "cream", "lotion", "moisturizer", "makeup", "mekap",
            "lipstick", "kajal", "compact", "powder", "perfume", "deo", "deodorant",
            "facewash", "hair oil", "shaving", "blade", "razor", "fair & lovely", "vaseline"
        ],
        "Dairy & Breakfast": [
            "milk", "doodh", "amul", "curd", "dahi", "paneer", "butter", "makkhan", "cheese",
            "bread", "egg", "anda", "cornflakes", "oats", "muesli"
        ],
        "Cleaning & Household": [
            "surf", "detergent", "washing powder", "ariel", "tide", "wheel", "rin", "vim",
            "dishwash", "bar", "harpic", "cleaner", "phenyl", "broom", "jhadu", "pocha",
            "agarbatti", "matchbox", "machis", "candle", "mosquito", "all out", "good knight"
        ],
        "Pharmacy & Healthcare": [
            "tablet", "capsule", "syrup", "paracetamol", "dolo", "crocin", "bandage", "bandaid",
            "dettol", "savlon", "balm", "vicks", "moov", "iodex", "cough", "antacid", "eno",
            "vitamin", "cotton", "mask", "sanitizer"
        ],
        "Stationery": [
            "pen", "pencil", "notebook", "copy", "register", "eraser", "sharpener", "scale",
            "marker", "glue", "fevicol", "stapler", "tape", "paper", "envelope"
        ],
    }

    # Match against taxonomy
    for cat, keywords in TAXONOMY.items():
        for kw in keywords:
            if kw in name:
                return JsonResponse({"category": cat, "confidence": "high"})

    # Check shop's existing categories for word overlap
    shop = request.user.profile.shop
    existing_cats = list(Product.objects.filter(shop=shop).values_list("category", flat=True).distinct())
    for cat in existing_cats:
        if cat and cat.lower() in name or name in cat.lower():
            return JsonResponse({"category": cat, "confidence": "medium"})

    # Optional AI fallback with Anthropic Claude API if available
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            prompt = f"Categorize this Indian retail shop product into one short 2-3 word category (e.g. Grocery, Snacks, Personal Care, Dairy, Stationery, Pharmacy, Cleaning): '{name}'. Return ONLY the category name."
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=20,
                messages=[{"role": "user", "content": prompt}]
            )
            suggested = response.content[0].text.strip()
            if suggested:
                return JsonResponse({"category": suggested, "confidence": "ai"})
        except Exception:
            pass

    return JsonResponse({"category": "General", "confidence": "fallback"})


@login_required
def barcode_generator(request):
    shop = request.user.profile.shop
    products = Product.objects.filter(shop=shop).order_by("name")
    stickers_per_product = int(request.GET.get("count", 10))
    selected_id = request.GET.get("product_id")

    if selected_id:
        products = products.filter(id=selected_id)

    # Generate sticker list
    sticker_list = []
    for p in products:
        barcode_val = getattr(p, "barcode", None) or f"{shop.id:03d}{p.id:05d}"
        for _ in range(stickers_per_product):
            sticker_list.append({
                "shop_name": shop.name,
                "name": p.name,
                "price": p.selling_price,
                "unit": p.get_unit_display(),
                "barcode": barcode_val,
            })

    return render(request, "inventory/barcode_stickers.html", {
        "stickers": sticker_list,
        "products": Product.objects.filter(shop=shop).order_by("name"),
        "selected_id": selected_id,
        "count": stickers_per_product,
    })


@login_required
def product_barcode(request, pk):
    shop = request.user.profile.shop
    product = get_object_or_404(Product, pk=pk, shop=shop)
    count = int(request.GET.get("count", 24))
    barcode_val = getattr(product, "barcode", None) or f"{shop.id:03d}{product.id:05d}"

    sticker_list = [{
        "shop_name": shop.name,
        "name": product.name,
        "price": product.selling_price,
        "unit": product.get_unit_display(),
        "barcode": barcode_val,
    } for _ in range(count)]

    return render(request, "inventory/barcode_stickers.html", {
        "stickers": sticker_list,
        "product": product,
        "count": count,
    })


@login_required
def apply_clearance_discount(request, pk):
    shop = request.user.profile.shop
    product = get_object_or_404(Product, pk=pk, shop=shop)
    if request.method == "POST":
        discount = int(request.POST.get("discount", 20))
        old_price = product.selling_price
        new_price = round(float(old_price) * (100 - discount) / 100, 2)
        product.selling_price = new_price
        product.save()

        log_activity(
            shop, request.user, "update", "inventory",
            f"Clearance Discount on {product.name}",
            f"Applied {discount}% clearance discount. Price reduced from Rs. {old_price} to Rs. {new_price}"
        )
        messages.success(request, f"⚡ Applied {discount}% Clearance Discount on '{product.name}'! New Price: Rs. {new_price}")
    return redirect("inventory:product_list")

