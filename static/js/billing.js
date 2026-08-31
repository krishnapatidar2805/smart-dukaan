(function () {
  let cart = []; // {product_id, name, standard_price, custom_price, qty, stock}
  let pointsDiscount = 0;

  const productSelect = document.getElementById("product-select");
  const qtyInput = document.getElementById("qty-input");
  const addBtn = document.getElementById("add-item-btn");
  const cartList = document.getElementById("cart-list");
  const itemsJsonField = document.getElementById("items-json");
  const discountInput = document.getElementById("discount-input");
  const gstInput = document.getElementById("gst-input");
  const subtotalEl = document.getElementById("subtotal-value");
  const totalEl = document.getElementById("total-value");
  const submitBtn = document.getElementById("submit-bill-btn");
  const anomalyAlertBox = document.getElementById("anomaly-alert-box");
  const pointsDiscountRow = document.getElementById("points-discount-row");
  const pointsDiscountVal = document.getElementById("points-discount-val");
  const posSearchInput = document.getElementById("pos-search-input");

  function money(n) {
    return "Rs. " + Number(n).toFixed(2);
  }

  function render() {
    cartList.innerHTML = "";
    if (cart.length === 0) {
      cartList.innerHTML = '<div class="empty-state" style="padding:20px;">No items in cart. Click any product above to add.</div>';
      if (anomalyAlertBox) anomalyAlertBox.style.display = "none";
    }
    let subtotal = 0;
    let hasAnomaly = false;

    cart.forEach((item, idx) => {
      const unitPrice = item.custom_price !== null && item.custom_price !== undefined ? item.custom_price : item.standard_price;
      const lineTotal = unitPrice * item.qty;
      subtotal += lineTotal;

      const diffPct = item.standard_price > 0 ? Math.abs(unitPrice - item.standard_price) / item.standard_price * 100 : 0;
      const isAnomaly = diffPct >= 30;
      if (isAnomaly) hasAnomaly = true;

      const row = document.createElement("div");
      row.className = "cart-item";
      row.style.display = "flex";
      row.style.justifyContent = "space-between";
      row.style.alignItems = "center";
      row.style.padding = "10px 0";
      row.style.borderBottom = "1px solid var(--border)";

      row.innerHTML = `
        <div style="flex:1;">
          <div style="font-weight:700; font-size:0.94rem;">${item.name}</div>
          <div style="font-size:0.82rem; color:var(--text-muted); display:flex; align-items:center; gap:8px; margin-top:2px;">
            <div style="display:inline-flex; align-items:center; border:1px solid var(--border); border-radius:6px; background:var(--surface);">
              <button type="button" class="btn-qty-minus" data-idx="${idx}" style="padding:2px 8px; border:none; background:none; cursor:pointer; font-weight:bold;">-</button>
              <span style="padding:0 6px; font-weight:700;">${item.qty}</span>
              <button type="button" class="btn-qty-plus" data-idx="${idx}" style="padding:2px 8px; border:none; background:none; cursor:pointer; font-weight:bold;">+</button>
            </div>
            <span>@ Rs. ${unitPrice.toFixed(2)}</span>
            ${isAnomaly ? `<span class="badge badge-danger" title="Standard price is Rs. ${item.standard_price}">⚠️ Price Anomaly (${Math.round(diffPct)}% diff)</span>` : ''}
          </div>
        </div>
        <div style="display:flex; align-items:center; gap:12px;">
          <strong style="font-size:1.05rem; color:var(--text);">${money(lineTotal)}</strong>
          <span class="remove" data-idx="${idx}" style="cursor:pointer; color:var(--danger); font-weight:bold; padding:4px 8px;">✕</span>
        </div>
      `;
      cartList.appendChild(row);
    });

    const manualDiscount = parseFloat(discountInput.value) || 0;
    const totalDiscount = manualDiscount + pointsDiscount;
    const gstPercent = parseFloat(gstInput.value) || 0;
    const gstAmount = subtotal * (gstPercent / 100);
    const total = Math.max(0, subtotal - totalDiscount + gstAmount);

    const isHighDiscount = subtotal > 0 && (totalDiscount / subtotal * 100) >= 25;
    if (isHighDiscount) hasAnomaly = true;

    subtotalEl.textContent = money(subtotal);
    totalEl.textContent = money(total);

    if (pointsDiscount > 0 && pointsDiscountRow && pointsDiscountVal) {
      pointsDiscountRow.style.display = "flex";
      pointsDiscountVal.textContent = `-Rs. ${pointsDiscount.toFixed(2)}`;
    } else if (pointsDiscountRow) {
      pointsDiscountRow.style.display = "none";
    }

    if (anomalyAlertBox) {
      if (hasAnomaly) {
        anomalyAlertBox.style.display = "block";
        anomalyAlertBox.innerHTML = `⚠️ <strong>Anomaly Detected:</strong> Price or discount deviation detected (>30% price change or >25% discount). This will be flagged in the Owner Audit Trail.`;
      } else {
        anomalyAlertBox.style.display = "none";
      }
    }

    itemsJsonField.value = JSON.stringify(
      cart.map((i) => ({
        product_id: i.product_id,
        qty: i.qty,
        custom_price: i.custom_price
      }))
    );

    // Quantity Increment / Decrement handlers
    document.querySelectorAll(".btn-qty-minus").forEach(btn => {
      btn.addEventListener("click", function() {
        const idx = parseInt(this.dataset.idx);
        if (cart[idx].qty > 1) {
          cart[idx].qty -= 1;
        } else {
          cart.splice(idx, 1);
        }
        render();
      });
    });

    document.querySelectorAll(".btn-qty-plus").forEach(btn => {
      btn.addEventListener("click", function() {
        const idx = parseInt(this.dataset.idx);
        if (cart[idx].qty < cart[idx].stock) {
          cart[idx].qty += 1;
        } else {
          alert(`Only ${cart[idx].stock} items available in stock!`);
        }
        render();
      });
    });

    document.querySelectorAll(".remove").forEach((el) => {
      el.addEventListener("click", function () {
        cart.splice(parseInt(this.dataset.idx), 1);
        render();
      });
    });

    submitBtn.disabled = cart.length === 0;
  }

  // Global function called by Visual POS tiles & voice search
  window.addToCartDirect = function(productId, name, price, stock, qty) {
    const existing = cart.find(i => String(i.product_id) === String(productId));
    if (existing) {
      if (existing.qty + qty > stock) {
        alert(`Cannot add more. Total in cart (${existing.qty + qty}) exceeds available stock (${stock}).`);
        return;
      }
      existing.qty += qty;
    } else {
      cart.push({
        product_id: productId,
        name: name,
        standard_price: price,
        custom_price: price,
        qty: qty,
        stock: stock
      });
    }
    render();
  };

  window.triggerCartRecalc = function(redeemedPoints) {
    pointsDiscount = parseFloat(redeemedPoints) || 0;
    render();
  };

  addBtn.addEventListener("click", function () {
    const qty = parseInt(qtyInput.value) || 1;
    const option = productSelect && productSelect.selectedIndex >= 0 ? productSelect.options[productSelect.selectedIndex] : null;

    if (option && option.value) {
      const productId = option.value;
      const price = parseFloat(option.dataset.price);
      const name = option.dataset.name;
      const stock = parseInt(option.dataset.stock);

      if (qty > stock) {
        alert(`Only ${stock} in stock for ${name}`);
        return;
      }

      window.addToCartDirect(productId, name, price, stock, qty);
      productSelect.selectedIndex = 0;
      qtyInput.value = 1;
      return;
    }

    // Check search input for matched product
    const term = posSearchInput ? posSearchInput.value.trim().toLowerCase() : "";
    if (term) {
      const tiles = document.querySelectorAll(".pos-tile");
      for (let i = 0; i < tiles.length; i++) {
        const tile = tiles[i];
        if (tile.style.display !== "none") {
          const tileName = tile.getAttribute("data-name").toLowerCase();
          if (tileName.includes(term) || term.includes(tileName)) {
            const pId = tile.getAttribute("data-id");
            const pName = tile.getAttribute("data-name");
            const pPrice = parseFloat(tile.getAttribute("data-price")) || 0;
            const pStock = parseInt(tile.getAttribute("data-stock")) || 0;
            if (pStock <= 0) {
              alert(`${pName} is out of stock!`);
              return;
            }
            window.addToCartDirect(pId, pName, pPrice, pStock, qty);
            posSearchInput.value = "";
            posSearchInput.dispatchEvent(new Event("input"));
            qtyInput.value = 1;
            return;
          }
        }
      }
    }

    alert("Please click a product card below or select a product to add to cart!");
  });

  // Barcode Gun Enter Key Handler
  if (posSearchInput) {
    posSearchInput.addEventListener("keydown", function(e) {
      if (e.key === "Enter") {
        e.preventDefault();
        const term = posSearchInput.value.trim().toLowerCase();
        if (!term) return;

        const tiles = document.querySelectorAll(".pos-tile");
        let matched = false;
        tiles.forEach(tile => {
          if (tile.style.display !== "none" && !matched) {
            const tileName = tile.getAttribute("data-name").toLowerCase();
            if (tileName.includes(term) || term.includes(tileName)) {
              tile.click();
              matched = true;
              posSearchInput.value = "";
              posSearchInput.dispatchEvent(new Event("input"));
            }
          }
        });
      }
    });
  }

  discountInput.addEventListener("input", render);
  gstInput.addEventListener("input", render);

  render();
})();
