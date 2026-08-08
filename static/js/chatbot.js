// templates/js/chatbot.js

const $ = id => document.getElementById(id);

const PRODUCT_IMAGE_BASE = 'https://gojoshop.et/storage/product/thumbnail/';

/* ==================================================================
   i18n / Language Manager
================================================================== */
const i18n = {
  _lang: localStorage.getItem('gojo_lang') || 'en',
  _data: {},

  get lang() { return this._lang; },

  t(key, fallback) {
    return this._data[key] ?? fallback ?? key;
  },

  async load(lang) {
    try {
      const res = await fetch(`/api/translations/${lang}`);
      if (!res.ok) throw new Error('Translation not found');
      this._data = await res.json();
      this._lang = lang;
      localStorage.setItem('gojo_lang', lang);
    } catch (e) {
      console.warn('Could not load translations for', lang, e);
    }
  },

  applyToDOM() {
    // Apply text translations
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.dataset.i18n;
      const val = this.t(key);
      if (val && val !== key) el.textContent = val;
    });
    // Apply placeholder translations
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.dataset.i18nPlaceholder;
      const val = this.t(key);
      if (val && val !== key) el.placeholder = val;
    });
    // Apply title/aria translations
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.dataset.i18nTitle;
      const val = this.t(key);
      if (val && val !== key) el.title = val;
    });
    // Apply aria-label translations
    document.querySelectorAll('[data-i18n-aria-label]').forEach(el => {
      const key = el.dataset.i18nAriaLabel;
      const val = this.t(key);
      if (val && val !== key) el.setAttribute('aria-label', val);
    });
    // Update html lang attribute
    document.getElementById('htmlRoot').lang = this._lang === 'am' ? 'am' : 'en';
    // Toggle Ethiopic font body class
    document.body.classList.toggle('lang-am', this._lang === 'am');
  }
};

function nowTime() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* Product card renderer */
function isProductCard(text) {
  return text.includes('PRODUCT SEARCH');
}

function parseProductCard(text) {
  const [resultText, recText = ''] = text.split('RECOMMENDATIONS');
  const filtersLine = resultText.split('\n').find(line => line.trim().startsWith('Filters:'));
  const hasMoreLine = resultText.split('\n').find(line => line.trim().startsWith('HasMore:'));

  function parseProducts(block) {
    const sections = block.split('\n---');
    const parsed = [];
    for (const sec of sections) {
      const lines = sec.split('\n');
      const prod = {};
      for (const line of lines) {
        const t = line.trim();
        if (!t || t.startsWith('Filters:') || t.startsWith('HasMore:') || t.includes('PRODUCT SEARCH')) continue;
        if (t.startsWith('Product ID:')) { prod.id = t.replace('Product ID:', '').trim(); continue; }
        if (t.startsWith('Name:')) { prod.name = t.replace('Name:', '').trim(); continue; }
        if (t.startsWith('Price:')) { prod.price = t.replace('Price:', '').trim(); continue; }
        if (t.startsWith('Stock:')) { prod.stock = t.replace('Stock:', '').trim(); continue; }
        if (t.startsWith('Image:')) { prod.image = t.replace('Image:', '').trim(); continue; }
        if (t.startsWith('Details:')) { prod.details = t.replace('Details:', '').trim(); continue; }
      }
      if (prod.id && prod.name) parsed.push(prod);
    }
    return parsed;
  }

  return {
    products: parseProducts(resultText),
    recommendations: parseProducts(recText),
    filters: filtersLine ? filtersLine.replace('Filters:', '').trim() : 'none',
    hasMore: hasMoreLine ? hasMoreLine.replace('HasMore:', '').trim() === 'true' : false,
  };
}

function getProductImage(name) {
  const keywords = ['toy', 'bear', 'earring', 'bag', 'backpack', 'purse', 'shoe', 'dress', 'shirt', 'towel', 'coaster', 'monkey', 'hippo'];
  const nameLower = name.toLowerCase();
  let foundKeyword = 'product';
  for (const kw of keywords) {
    if (nameLower.includes(kw)) { foundKeyword = kw; break; }
  }
  const images = {
    toy: 'https://images.unsplash.com/photo-1559251606-c623743a6d76?auto=format&fit=crop&w=400&q=80',
    bear: 'https://images.unsplash.com/photo-1582060047814-1237a2f2a75d?auto=format&fit=crop&w=400&q=80',
    monkey: 'https://images.unsplash.com/photo-1540573133985-87b6da6d54a9?auto=format&fit=crop&w=400&q=80',
    hippo: 'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?auto=format&fit=crop&w=400&q=80',
    earring: 'https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=400&q=80',
    bag: 'https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=400&q=80',
    backpack: 'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=400&q=80',
    purse: 'https://images.unsplash.com/photo-1566150905458-1bf1fc15a7a5?auto=format&fit=crop&w=400&q=80',
    shoe: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=400&q=80',
    dress: 'https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=400&q=80',
    shirt: 'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=400&q=80',
    towel: 'https://images.unsplash.com/photo-1563453392212-326f5e854473?auto=format&fit=crop&w=400&q=80',
    coaster: 'https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=400&q=80',
    product: 'https://images.unsplash.com/photo-1472851294608-062f824d29cc?auto=format&fit=crop&w=400&q=80'
  };
  return images[foundKeyword];
}

function resolveProductImage(thumbnail, name) {
  if (thumbnail && thumbnail.startsWith('http')) return thumbnail;
  if (thumbnail && thumbnail !== 'def.png') return PRODUCT_IMAGE_BASE + thumbnail;
  return getProductImage(name);
}

const cartIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>`;

function ensureProductPreviewModal() {
  let modal = document.getElementById('productImageModal');
  if (modal) return modal;
  modal = document.createElement('div');
  modal.id = 'productImageModal';
  modal.className = 'product-image-modal';
  modal.innerHTML = `
    <div class="product-image-modal-backdrop" onclick="closeProductPreview()"></div>
    <div class="product-image-modal-panel">
      <button class="product-image-modal-close" onclick="closeProductPreview()" aria-label="Close image">&times;</button>
      <img class="product-image-modal-img" alt="Product preview" />
      <div class="product-image-modal-title"></div>
    </div>`;
  document.body.appendChild(modal);
  const panel = modal.querySelector('.product-image-modal-panel');
  panel.addEventListener('click', e => e.stopPropagation());
  return modal;
}

function openProductPreview(imageUrl, title) {
  const modal = ensureProductPreviewModal();
  const img = modal.querySelector('.product-image-modal-img');
  const label = modal.querySelector('.product-image-modal-title');
  img.src = imageUrl || '';
  img.alt = title || 'Product preview';
  label.textContent = title || 'Product preview';
  modal.classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeProductPreview() {
  const modal = document.getElementById('productImageModal');
  if (!modal) return;
  modal.classList.remove('active');
  document.body.style.overflow = '';
}

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeProductPreview();
});

function renderProductCards(products) {
  return products.map(p => {
    const isOutOfStock = parseInt(p.stock) <= 0;
    const stockClass = isOutOfStock ? 'stock-out' : 'stock-available';
    const stockText = isOutOfStock
      ? i18n.t('out_of_stock', 'Out of stock')
      : i18n.t('in_stock_count', '{count} in stock').replace('{count}', p.stock);
    const imgUrl = resolveProductImage(p.image, p.name);
    const safeName = escHtml(p.name);
    const safeDetails = escHtml(p.details);
    const safeImage = escHtml(imgUrl);
    const safePrice = escHtml(p.price);
    const safeStockText = escHtml(stockText);
    const productId = Number.parseInt(p.id, 10);
    const desc = safeDetails ? `<p class="product-desc">${safeDetails}</p>` : '';
    const previewImage = imgUrl.replace(/'/g, "\\'");
    const previewName = String(p.name || '').replace(/'/g, "\\'");
    return `
      <div class="product-card">
        <div
          class="product-img"
          style="background-image:url('${safeImage}')"
          role="button"
          tabindex="0"
          onclick="openProductPreview('${previewImage}', '${previewName}')"
          onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); openProductPreview('${previewImage}', '${previewName}');}"
        >
          <div class="product-price-badge">${safePrice}</div>
        </div>
        <div class="product-info">
          <h3 class="product-title" title="${safeName}">${safeName}</h3>
          ${desc}
          <span class="product-stock ${stockClass}"><span class="stock-dot"></span>${safeStockText}</span>
          <button class="add-cart-btn" data-product-name="${safeName}" onclick="addCartClicked(this, ${productId})" ${isOutOfStock ? 'disabled' : ''}>
            ${isOutOfStock ? i18n.t('sold_out', 'Sold Out') : cartIcon + ' ' + i18n.t('add_btn', 'Add')}
          </button>
        </div>
      </div>`;
  }).join('');
}

function formatFilters(filters) {
  if (!filters || filters === 'none') return i18n.t('no_filters', 'No filters applied');
  return filters
    .replace(/min_price=/g, i18n.t('min_label', 'Min') + ' ')
    .replace(/max_price=/g, i18n.t('max_label', 'Max') + ' ')
    .replace(/in_stock=true/g, i18n.t('in_stock_label', 'In stock'))
    .replace(/sort=price_asc/g, i18n.t('cheapest_first', 'Cheapest first'))
    .replace(/sort=price_desc/g, i18n.t('highest_price_first', 'Highest price first'))
    .replace(/sort=newest/g, i18n.t('newest_first', 'Newest first'))
    .replace(/;/g, ' · ');
}

function renderProductGrid(data) {
  const products = data.products || [];
  const recommendations = data.recommendations || [];
  const cards = renderProductCards(products);
  const recCards = renderProductCards(recommendations);
  const count = products.length;
  const prodWord = count === 1 ? i18n.t('product', 'product') : i18n.t('products', 'products');
  const label = `${count} ${prodWord}`;
  const activeFilters = formatFilters(data.filters);
  const filterButtons = [
    [i18n.t('in_stock_label', 'In stock'), ' in stock'],
    [i18n.t('cheapest_first', 'Cheapest'), ' cheapest'],
    [i18n.t('newest_first', 'Newest'), ' newest'],
    ['Under 1000', ' under 1000'],
  ].map(([labelText, suffix]) =>
    `<button class="filter-btn" onclick="applyProductFilter('${suffix}')">${labelText}</button>`
  ).join('');
  const recSection = recommendations.length
    ? `<div class="recommendation-section"><div class="recommendation-title">${i18n.t('rec_alternatives', 'Recommended alternatives')}</div><div class="product-track">${recCards}</div></div>`
    : '';
  const showMoreBtn = data.hasMore
    ? `<button class="show-more-btn" onclick="showMoreProducts()">${i18n.t('show_more', 'Show more')}</button>`
    : '';
  return `
    <div class="product-results">
      <div class="product-results-header">
        <h3>${i18n.t('search_results', 'Search Results')}</h3>
        <span class="product-count">${label}</span>
      </div>
      <div class="product-filter-bar">${filterButtons}</div>
      <div class="active-filters">${escHtml(activeFilters)}</div>
      <div class="product-track">${cards}</div>
      ${showMoreBtn}
      ${recSection}
    </div>`;
}

function isSupportCard(text) {
  return text.includes('━━━ HUMAN SUPPORT ━━━');
}

function parseSupportCard(text) {
  const lines = text.split('\n').filter(l => l.trim() && !l.startsWith('━━━'));
  const data = { intro: '' };
  const marker = '━━━ HUMAN SUPPORT ━━━';
  const parts = text.split(marker);
  if (parts[0]) data.intro = parts[0].trim();
  for (const line of lines) {
    const t = line.trim();
    if (t.startsWith('Shop:')) data.shop = t.replace('Shop:', '').trim();
    if (t.startsWith('Email:')) data.email = t.replace('Email:', '').trim();
    if (t.startsWith('Phone:')) data.phone = t.replace('Phone:', '').trim();
    if (t.startsWith('Hours:')) data.hours = t.replace('Hours:', '').trim();
    if (t.startsWith('Note:')) data.note = t.replace('Note:', '').trim();
  }
  return data;
}

function renderSupportCard(data) {
  const intro = data.intro
    ? `<p class="support-intro">${data.intro.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')}</p>`
    : '';
  const email = data.email || 'support@gojoshop.et';
  const phone = (data.phone || '+251988664488').replace(/\s/g, '');
  return `
    <div class="support-card">
      ${intro}
      <div class="support-card-header">
        <span class="support-badge">${i18n.t('human_support_badge', '💬 Human Support')}</span>
        <span class="support-shop">${data.shop || 'GojoShop.et'}</span>
      </div>
      <div class="support-actions">
        <a class="support-btn email" href="mailto:${email}">${i18n.t('email_us_btn', '📧 Email us')}</a>
        <a class="support-btn phone" href="tel:${phone}">${i18n.t('call_us_btn', '📞 Call us')}</a>
      </div>
      <div class="support-meta">
        <div><strong>${i18n.t('email_label', 'Email')}</strong><span>${email}</span></div>
        <div><strong>${i18n.t('phone_label', 'Phone')}</strong><span>${data.phone || phone}</span></div>
        <div><strong>${i18n.t('hours_label', 'Hours')}</strong><span>${data.hours || 'Mon–Sat, 9–6 EAT'}</span></div>
      </div>
      ${data.note ? `<p class="support-note">${data.note}</p>` : ''}
    </div>`;
}

function isOrderCard(text) {
  return text.startsWith('━━━') && !text.includes('PRODUCT SEARCH') && !isSupportCard(text);
}

/* Checkout card renderer */
function isCheckoutCard(text) {
  return text.startsWith('[CHECKOUT]');
}

function parseCheckoutCard(text) {
  const data = { items: [] };
  for (const line of text.split('\n')) {
    const t = line.trim();
    if (!t || t.startsWith('[')) continue;
    if (t.startsWith('Step:')) data.step = t.replace('Step:', '').trim();
    else if (t.startsWith('Name:')) data.name = t.replace('Name:', '').trim();
    else if (t.startsWith('Phone:')) data.phone = t.replace('Phone:', '').trim();
    else if (t.startsWith('Address:')) data.address = t.replace('Address:', '').trim();
    else if (t.startsWith('Payment:')) data.payment = t.replace('Payment:', '').trim();
    else if (t.startsWith('Total:')) data.total = t.replace('Total:', '').trim();
    else if (t.startsWith('Prompt:')) data.prompt = t.replace('Prompt:', '').trim();
    else if (t.startsWith('Item:')) data.items.push(t.replace('Item:', '').trim());
  }
  return data;
}

const _checkoutLinkHtml = '<a href="#" class="checkout-link" onclick="event.preventDefault(); document.getElementById(\'msgInput\').value=\'Checkout\'; document.getElementById(\'sendBtn\').click();">';
function linkifyCheckout(html) {
  return html
    .replace(/<(code|strong)>([^<]*?\b)(checkout)\b([^<]*?)<\/\1>/gi, (m, tag, pre, word, post) =>
      `<${tag}>${pre}${_checkoutLinkHtml}${word}</a>${post}</${tag}>`)
    .replace(/(?<!<[^>]*)\b(checkout)\b(?![^<]*>)/gi, (m, word) =>
      `${_checkoutLinkHtml}${word}</a>`);
}

function renderCheckoutCard(data) {
  const safeName = escHtml(data.name || '');
  const safePhone = escHtml(data.phone || '');
  const safeAddress = escHtml(data.address || '');
  const safePayment = escHtml(data.payment || '');
  const safeTotal = escHtml(data.total || '');
  const safePrompt = escHtml(data.prompt || '');
  const removeLabel = i18n.t('cart_remove_btn', '✕ Remove');
  const clearLabel = i18n.t('clear_cart_btn', 'Clear Cart');
  const clearTooltip = i18n.t('clear_cart_tooltip', 'Clear all items in cart');
  const itemsHtml = data.items.length
    ? data.items.map(i => {
        const name = String(i).split(' × ')[0];
        const safeItemName = escHtml(name);
        return `<li class="cart-item-row"><span>${escHtml(i)}</span>` +
               `<button type="button" class="cart-remove-btn" data-product-name="${safeItemName}" ` +
               `title="${escHtml(removeLabel)}" onclick="removeCartClicked(this)">✕</button></li>`;
      }).join('')
    : '<li>—</li>';
  return `
    <div class="checkout-card">
      <div class="checkout-card-header">
        <span class="checkout-badge">${i18n.t('checkout_review_badge', '🛒 Review Your Order')}</span>
        ${data.items.length ? `<button type="button" class="cart-clear-btn" title="${escHtml(clearTooltip)}" onclick="clearCartClicked(this)">✕ ${escHtml(clearLabel)}</button>` : ''}
      </div>
      <div class="checkout-card-info">
        <div class="checkout-row"><span>👤 ${i18n.t('name_label', 'Name')}</span><b>${safeName}</b></div>
        <div class="checkout-row"><span>📞 ${i18n.t('phone_label', 'Phone')}</span><b>${safePhone}</b></div>
        <div class="checkout-row"><span>📍 ${i18n.t('address_label', 'Address')}</span><b>${safeAddress}</b></div>
        <div class="checkout-row"><span>💳 ${i18n.t('payment_label', 'Payment')}</span><b>${safePayment}</b></div>
      </div>
      <ul class="checkout-items">${itemsHtml}</ul>
      <div class="checkout-total">💰 ${i18n.t('total_label', 'Total')}: <b>${safeTotal}</b></div>
      ${safePrompt ? `<p class="checkout-prompt">${linkifyCheckout(safePrompt.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>'))}</p>` : ''}
    </div>`;
}

/* Cart card renderer */
function isCartCard(text) {
  return text.includes('[CART]');
}

function parseCartCard(text) {
  const data = { items: [] };
  for (const line of text.split('\n')) {
    const t = line.trim();
    if (!t || t.startsWith('[')) continue;
    if (t.startsWith('Msg:')) data.msg = t.replace('Msg:', '').trim();
    else if (t.startsWith('Total:')) data.total = t.replace('Total:', '').trim();
    else if (t.startsWith('Prompt:')) data.prompt = t.replace('Prompt:', '').trim();
    else if (t.startsWith('Item:')) data.items.push(t.replace('Item:', '').trim());
  }
  return data;
}

function renderCartCard(data) {
  const safeTotal = escHtml(data.total || '');
  const safePrompt = escHtml(data.prompt || '');
  const safeMsg = escHtml(data.msg || '');
  const removeLabel = i18n.t('cart_remove_btn', '✕ Remove');
  const clearLabel = i18n.t('clear_cart_btn', 'Clear Cart');
  const clearTooltip = i18n.t('clear_cart_tooltip', 'Clear all items in cart');
  const itemsHtml = data.items.length
    ? data.items.map(i => {
        const name = String(i).split(' × ')[0];
        const safeName = escHtml(name);
        return `<li class="cart-item-row"><span>${escHtml(i)}</span>` +
               `<button type="button" class="cart-remove-btn" data-product-name="${safeName}" ` +
               `title="${escHtml(removeLabel)}" onclick="removeCartClicked(this)">✕</button></li>`;
      }).join('')
    : '<li>—</li>';
  return `
    ${safeMsg ? `<p class="cart-msg">${safeMsg}</p>` : ''}
    <div class="checkout-card">
      <div class="checkout-card-header">
        <span class="checkout-badge">${i18n.t('cart_badge', '🛒 Your Cart')}</span>
        ${data.items.length ? `<button type="button" class="cart-clear-btn" title="${escHtml(clearTooltip)}" onclick="clearCartClicked(this)">✕ ${escHtml(clearLabel)}</button>` : ''}
      </div>
      <ul class="checkout-items">${itemsHtml}</ul>
      <div class="checkout-total">💰 ${i18n.t('total_label', 'Total')}: <b>${safeTotal}</b></div>
      ${safePrompt ? `<p class="checkout-prompt">${linkifyCheckout(safePrompt.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>'))}</p>` : ''}
    </div>`;
}

/* Promo card renderer */
function isPromoCard(text) {
  return text.includes('PROMO');
}

function parsePromoCard(text) {
  const data = {};
  for (const line of text.split('\n')) {
    const t = line.trim();
    if (!t || t === 'PROMO') continue;
    if (t.startsWith('Intro:')) data.intro = t.replace('Intro:', '').trim();
    else if (t.startsWith('Title:')) data.title = t.replace('Title:', '').trim();
    else if (t.startsWith('Name:')) data.name = t.replace('Name:', '').trim();
    else if (t.startsWith('Price:')) data.price = t.replace('Price:', '').trim();
    else if (t.startsWith('Discount:')) data.discount = t.replace('Discount:', '').trim();
    else if (t.startsWith('Details:')) data.details = t.replace('Details:', '').trim();
    else if (t.startsWith('Image:')) data.image = t.replace('Image:', '').trim();
    else if (t.startsWith('Id:')) data.id = t.replace('Id:', '').trim();
  }
  return data;
}

function renderPromoCard(data) {
  const safeName = escHtml(data.name || '');
  const safeTitle = escHtml(data.title || '');
  const safePrice = escHtml(data.price || '');
  const safeDetails = escHtml(data.details || '');
  const discountMatch = (data.discount || '').match(/([\d.]+)/);
  const discountPct = discountMatch ? discountMatch[1] : '';
  const imgUrl = resolveProductImage(data.image, data.name);
  const safeImage = escHtml(imgUrl);
  const productId = Number.parseInt(data.id, 10);
  const previewImage = imgUrl.replace(/'/g, "\\'");
  const previewName = String(data.name || '').replace(/'/g, "\\'");
  const intro = data.intro
    ? `<p class="promo-intro">${data.intro.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')}</p>`
    : '';
  const discountBadge = discountPct
    ? `<span class="promo-discount-badge">${escHtml(discountPct)}% ${i18n.t('promo_off', 'OFF')}</span>`
    : '';
  const title = safeTitle
    ? `<div class="promo-title-tag">${safeTitle}</div>`
    : '';
  return `
    ${intro}
    <div class="promo-card">
      <div class="promo-card-img" style="background-image:url('${safeImage}')" role="button" tabindex="0"
        onclick="openProductPreview('${previewImage}', '${previewName}')"
        onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault(); openProductPreview('${previewImage}', '${previewName}');}">
        ${discountBadge}
      </div>
      <div class="promo-card-info">
        ${title}
        <h3 class="promo-card-name" title="${safeName}">${safeName}</h3>
        <div class="promo-card-price">${safePrice}</div>
        ${safeDetails ? `<p class="promo-card-details">${safeDetails}</p>` : ''}
        <button class="add-cart-btn" data-product-name="${safeName}" onclick="addCartClicked(this, ${productId})">
          ${cartIcon + ' ' + i18n.t('add_btn', 'Add')}
        </button>
      </div>
    </div>`;
}

const STATUS_CLASS = {
  DELIVERED: 'status-delivered', SHIPPED: 'status-shipped',
  PROCESSING: 'status-processing', PENDING: 'status-pending', CANCELLED: 'status-cancelled',
};
const STATUS_EMOJI = {
  DELIVERED: '✅', SHIPPED: '🚚', PROCESSING: '⚙️', PENDING: '🕒', CANCELLED: '✖️'
};

function parseOrderCard(text) {
  const lines = text.split('\n').filter(l => !l.startsWith('━━━'));
  const data = {}; const items = []; let inItems = false;
  for (const line of lines) {
    const t = line.trim();
    if (!t) continue;

    // ── Order header ──────────────────────────────────────────
    if (t.startsWith('📦')) { data.order_id = t.replace(/^📦\s*Order\s*#?/i, '').trim(); continue; }
    if (t.startsWith('🗂️')) { data.group = t.replace(/^🗂️\s*Group\s*:/i, '').trim(); continue; }

    // ── Customer block ─────────────────────────────────────────
    if (t.startsWith('👤')) { data.customer = t.replace(/^👤\s*Customer\s*:/i, '').trim(); continue; }
    if (t.startsWith('📱')) { data.phone = t.replace(/^📱\s*Phone\s*:/i, '').trim(); continue; }
    if (t.startsWith('📧')) { data.email = t.replace(/^📧\s*Email\s*:/i, '').trim(); continue; }

    // ── Timestamps ─────────────────────────────────────────────
    if (t.startsWith('📅')) { data.placed = t.replace(/^📅\s*Placed\s*:/i, '').trim(); continue; }
    if (t.startsWith('🔄')) { data.updated = t.replace(/^🔄\s*Updated\s*:/i, '').trim(); continue; }

    // ── Delivery block ─────────────────────────────────────────
    if (/^[📦🕐⚙️🚚✅❌]\s*Status\s*:/i.test(t)) {
      const m = t.match(/Status\s*:\s*(.+)/i);
      data.status = m ? m[1].trim().toUpperCase() : '';
      continue;
    }
    if (t.startsWith('🚚') && t.includes('Tracking')) { data.tracking = t.replace(/^🚚\s*Tracking\s*:/i, '').trim(); continue; }
    if (t.startsWith('📆')) { data.expected = t.replace(/^📆\s*Expected\s*:/i, '').trim(); continue; }
    if (t.startsWith('📍')) { data.delivery = t.replace(/^📍\s*Delivery\s*:/i, '').trim(); continue; }
    if (t.startsWith('🏠')) { data.address = t.replace(/^🏠\s*Address\s*:/i, '').trim(); continue; }
    if (t.startsWith('📝')) { data.note = t.replace(/^📝\s*Note\s*:/i, '').trim(); continue; }

    // ── Items block ────────────────────────────────────────────
    if (t.startsWith('🛍️')) { inItems = true; continue; }
    if (inItems && t.startsWith('•')) {
      const m = t.match(/•\s+(.+?)\s+×\s+(\d+)\s+—\s+([^\s]+\s*ETB)/);
      if (m) {
        const rest = t.slice(m[0].length).trim();
        const variant = (rest.match(/\[([^\]]+)\]/) || [])[1] || '';
        items.push({ name: m[1], qty: m[2], price: m[3], variant });
      }
      continue;
    }
    if (inItems && !t.startsWith('•')) inItems = false;

    // ── Payment block ──────────────────────────────────────────
    if (t.startsWith('💳')) { data.payment = t.replace(/^💳\s*Payment\s*:/i, '').trim(); inItems = false; continue; }
    if (t.startsWith('🔢')) { data.tx_ref = t.replace(/^🔢\s*Tx Ref\s*:/i, '').trim(); continue; }
    if (t.startsWith('🏷️') && t.includes('Coupon')) { data.coupon = t.replace(/^🏷️\s*Coupon\s*:/i, '').trim(); continue; }
    if (t.startsWith('💸')) { data.discount = t.replace(/^💸\s*Discount\s*:/i, '').trim(); continue; }
    if (t.startsWith('🚚') && t.includes('Shipping')) { data.shipping = t.replace(/^🚚\s*Shipping\s*:/i, '').trim(); continue; }
    if (t.startsWith('💰')) { data.total = t.replace(/^💰\s*Total\s*:/i, '').trim(); continue; }
    if (t.startsWith('🏢')) { data.seller = t.replace(/^🏢\s*Seller\s*:/i, '').trim(); continue; }

    // ── Cancellation block ─────────────────────────────────────
    if (t.startsWith('❌') && t.includes('Reason')) { data.cancel_reason = t.replace(/^❌\s*Reason\s*:/i, '').trim(); continue; }
    if (t.startsWith('🔍')) { data.cancel_cause = t.replace(/^🔍\s*Cause ID\s*:/i, '').trim(); continue; }
    if (t.startsWith('👁️')) { data.canceled_by = t.replace(/^👁️\s*Cancelled by\s*:/i, '').trim(); continue; }

    // Status footer message (non-prefixed trailing text)
    if (!inItems && data.total && !t.startsWith('•')) data.statusMsg = t;
  }
  data.items = items;
  return data;
}

function renderOrderCard(data) {
  const rawStatus = (data.status || '').toUpperCase().replace('CANCELED', 'CANCELLED');
  const sc = STATUS_CLASS[rawStatus] || 'status-pending';
  const se = STATUS_EMOJI[rawStatus] || '📦';

  const itemRows = data.items.map(it => {
    const variant = it.variant ? `<span class="oc-item-variant">${escHtml(it.variant)}</span>` : '';
    return `<li><span>${escHtml(it.name)} × ${escHtml(it.qty)}${variant}</span><span>${escHtml(it.price)}</span></li>`;
  }).join('') || `<li class="oc-no-items">${i18n.t('no_items', 'No items found.')}</li>`;

  const cancelBlock = data.cancel_reason
    ? `<hr class="oc-divider"/>
       <div class="oc-row"><span class="oc-label">❌ ${i18n.t('cancel_reason_label', 'Reason')}</span><span class="oc-val oc-cancel">${escHtml(data.cancel_reason)}</span></div>
       ${data.cancel_cause ? `<div class="oc-row"><span class="oc-label">🔍 ${i18n.t('cancel_cause_label', 'Cause ID')}</span><span class="oc-val">${escHtml(data.cancel_cause)}</span></div>` : ''}
       ${data.canceled_by ? `<div class="oc-row"><span class="oc-label">👁️ ${i18n.t('canceled_by_label', 'By')}</span><span class="oc-val">${escHtml(data.canceled_by)}</span></div>` : ''}`
    : '';

  return `
    <div class="order-card">
      <div class="oc-row"><span class="oc-label">${i18n.t('order_id_label', 'Order ID')}</span><span class="oc-val oc-id">#${escHtml(data.order_id || '—')}</span></div>
      ${data.group ? `<div class="oc-row"><span class="oc-label">${i18n.t('order_group_label', 'Group')}</span><span class="oc-val oc-muted">${escHtml(data.group)}</span></div>` : ''}
      <hr class="oc-divider"/>
      <div class="oc-row"><span class="oc-label">${i18n.t('customer_label', 'Customer')}</span><span class="oc-val"><strong>${escHtml(data.customer || '—')}</strong></span></div>
      ${data.phone ? `<div class="oc-row"><span class="oc-label">📱 ${i18n.t('phone_label', 'Phone')}</span><span class="oc-val">${escHtml(data.phone)}</span></div>` : ''}
      ${data.email ? `<div class="oc-row"><span class="oc-label">📧 ${i18n.t('email_label', 'Email')}</span><span class="oc-val">${escHtml(data.email)}</span></div>` : ''}
      <hr class="oc-divider"/>
      <div class="oc-row"><span class="oc-label">${i18n.t('placed_label', 'Placed')}</span><span class="oc-val">${escHtml(data.placed || '—')}</span></div>
      ${data.updated ? `<div class="oc-row"><span class="oc-label">${i18n.t('updated_label', 'Updated')}</span><span class="oc-val">${escHtml(data.updated)}</span></div>` : ''}
      <hr class="oc-divider"/>
      <div class="oc-row"><span class="oc-label">${i18n.t('status_label', 'Status')}</span><span class="status-badge ${sc}">${se} ${rawStatus || '—'}</span></div>
      <div class="oc-row"><span class="oc-label">${i18n.t('tracking_label', 'Tracking')}</span><span class="oc-val">${escHtml(data.tracking || '—')}</span></div>
      ${data.expected ? `<div class="oc-row"><span class="oc-label">${i18n.t('expected_label', 'Expected')}</span><span class="oc-val">${escHtml(data.expected)}</span></div>` : ''}
      ${data.delivery ? `<div class="oc-row"><span class="oc-label">${i18n.t('delivery_type_label', 'Delivery')}</span><span class="oc-val">${escHtml(data.delivery)}</span></div>` : ''}
      <div class="oc-row"><span class="oc-label">${i18n.t('delivery_label', 'Address')}</span><span class="oc-val">${escHtml(data.address || '—')}</span></div>
      ${data.note && data.note !== '—' ? `<div class="oc-row"><span class="oc-label">${i18n.t('note_label', 'Note')}</span><span class="oc-val oc-muted">${escHtml(data.note)}</span></div>` : ''}
      <hr class="oc-divider"/>
      <ul class="oc-items-list">${itemRows}</ul>
      <hr class="oc-divider"/>
      <div class="oc-row"><span class="oc-label">${i18n.t('payment_label', 'Payment')}</span><span class="oc-val">${escHtml(data.payment || '—')}</span></div>
      ${data.tx_ref && data.tx_ref !== 'N/A' ? `<div class="oc-row"><span class="oc-label">${i18n.t('tx_ref_label', 'Tx Ref')}</span><span class="oc-val oc-muted">${escHtml(data.tx_ref)}</span></div>` : ''}
      ${data.coupon && data.coupon !== '—' ? `<div class="oc-row"><span class="oc-label">🏷️ ${i18n.t('coupon_label', 'Coupon')}</span><span class="oc-val">${escHtml(data.coupon)}</span></div>` : ''}
      ${data.discount ? `<div class="oc-row"><span class="oc-label">💸 ${i18n.t('discount_label', 'Discount')}</span><span class="oc-val">${escHtml(data.discount)}</span></div>` : ''}
      <div class="oc-row"><span class="oc-label">🚚 ${i18n.t('shipping_label', 'Shipping')}</span><span class="oc-val">${escHtml(data.shipping || '—')}</span></div>
      <div class="oc-row"><span class="oc-label">${i18n.t('total_label', 'Total')}</span><span class="oc-val oc-total">${escHtml(data.total || '—')}</span></div>
      ${data.seller && data.seller !== 'N/A' ? `<div class="oc-row"><span class="oc-label">🏢 ${i18n.t('seller_label', 'Seller')}</span><span class="oc-val oc-muted">${escHtml(data.seller)}</span></div>` : ''}
      ${cancelBlock}
      ${data.statusMsg ? `<hr class="oc-divider"/><div class="oc-status-msg">${escHtml(data.statusMsg)}</div>` : ''}
    </div>`;
}


/* ==================================================================
   Live Support Polling
================================================================== */
const SupportPoller = {
  _interval: null,
  _lastCount: 0,
  _requestId: null,

  start(userId, chat) {
    this._lastCount = 0;
    this._requestId = null;
    this._interval = setInterval(() => this._poll(userId, chat), 3000);
    this._poll(userId, chat);
  },

  stop() {
    if (this._interval) { clearInterval(this._interval); this._interval = null; }
    this._lastCount = 0;
    this._requestId = null;
  },

  async _poll(userId, chat) {
    try {
      const res = await fetch(`/api/support/requests/active/${encodeURIComponent(userId)}`);
      const data = await res.json();
      // Abort if we are no longer in support mode (e.g. turned off by send())
      if (!chat._inSupportMode) {
        this.stop();
        return;
      }
      if (data.status !== 'active') {
        // Support session ended by agent
        this.stop();
        chat._setSupportMode(false);
        chat._appendBotWithDelay(i18n.t('active_support_ended', '✅ Support session has ended. How else can I help you?'), 0, false);
        return;
      }
      this._requestId = data.request_id;
      const messages = data.messages || [];
      // Only show new messages since last poll
      const newMsgs = messages.slice(this._lastCount);
      this._lastCount = messages.length;
      for (const msg of newMsgs) {
        if (msg.sender === 'agent') {
          chat._appendAgentMessage(msg.text);
        }
      }
    } catch (e) {
      console.warn('Support poll error:', e);
    }
  }
};

/* ==================================================================
   GojoChat class
================================================================== */
class GojoChat {
  constructor() {
    this.userId = localStorage.getItem('gojo_uid') || this._genId();
    localStorage.setItem('gojo_uid', this.userId);
    this.input = $('msgInput');
    this.sendBtn = $('sendBtn');
    this.messages = $('chatMessages');
    this.typing = $('typingRow');
    this.lastProductQuery = localStorage.getItem('gojo_last_product_query') || '';
    this._inSupportMode = false;
    this._unreadCount = 0;
    this._initChatWindow();
    $('welcomeTs').textContent = nowTime();
    this._initLang();
    this._bind();
    this._restoreAiState();
    this._refreshCartBadge();
  }

  _genId() { return 'u_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9); }

  _initChatWindow() {
    const saved = localStorage.getItem('gojo_chat_open');
    const isOpen = saved === null ? true : saved === '1';
    document.body.classList.toggle('chat-open', isOpen);
    document.body.classList.toggle('chat-closed', !isOpen);
    this._updateBubbleBadge();
  }

  _isChatOpen() {
    return document.body.classList.contains('chat-open');
  }

  _setChatOpen(open) {
    document.body.classList.toggle('chat-open', open);
    document.body.classList.toggle('chat-closed', !open);
    localStorage.setItem('gojo_chat_open', open ? '1' : '0');
    if (open) {
      this._unreadCount = 0;
      this._updateBubbleBadge();
      setTimeout(() => this.input.focus(), 350);
    }
  }

  _updateBubbleBadge() {
    const badge = $('chatBubbleCount');
    if (!badge) return;
    badge.hidden = this._unreadCount === 0;
    badge.textContent = this._unreadCount > 99 ? '99+' : String(this._unreadCount);
  }

  _bumpUnread() {
    this._unreadCount += 1;
    this._updateBubbleBadge();
  }

  async _refreshCartBadge() {
    const badge = $('cartCount');
    if (!badge) return;
    try {
      const res = await fetch(`/api/cart/details/${encodeURIComponent(this.userId)}`);
      if (!res.ok) throw new Error('cart fetch failed');
      const data = await res.json();
      const count = Array.isArray(data.items) ? data.items.length : 0;
      badge.hidden = count === 0;
      badge.textContent = count > 99 ? '99+' : String(count);
    } catch (_) {
      badge.hidden = true;
    }
  }

  _showCart() {
    if (!this._isChatOpen()) {
      this._setChatOpen(true);
    }
    this.input.value = 'cart';
    this.input.focus();
    this.send();
  }

  _playNotifySound() {
    try {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (!Ctx) return;
      const ctx = this._audioCtx || (this._audioCtx = new Ctx());
      if (ctx.state === 'suspended') ctx.resume();
      const now = ctx.currentTime;
      const makeTone = (freq, start, dur) => {
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'sine';
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0, start);
        gain.gain.linearRampToValueAtTime(0.18, start + 0.02);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + dur);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(start);
        osc.stop(start + dur + 0.05);
      };
      makeTone(880, now, 0.28);
      makeTone(1174.66, now + 0.18, 0.32);
    } catch (e) {
      console.warn('Notification sound error:', e);
    }
  }

  async _initLang() {
    const savedLang = i18n.lang;
    await i18n.load(savedLang);
    i18n.applyToDOM();
    this._updateLangBtns(savedLang);
    this._maybeShowFeaturedPromo();
  }

  async _maybeShowFeaturedPromo() {
    try {
      const res = await fetch(`/api/promotions/featured?lang=${encodeURIComponent(i18n.lang)}&user_id=${encodeURIComponent(this.userId)}`);
      if (!res.ok) return;
      const data = await res.json();
      if (data.promo && data.promo.card) {
        await this._appendBotWithDelay(data.promo.card, 300, false);
      }
    } catch (e) {
      console.warn('Featured promo load error:', e);
    }
  }

  _updateLangBtns(lang) {
    const enBtn = $('langBtnEn');
    const amBtn = $('langBtnAm');
    if (!enBtn || !amBtn) return;
    enBtn.classList.toggle('active', lang === 'en');
    enBtn.setAttribute('aria-pressed', String(lang === 'en'));
    amBtn.classList.toggle('active', lang === 'am');
    amBtn.setAttribute('aria-pressed', String(lang === 'am'));
  }

  _bind() {
    this.sendBtn.addEventListener('click', () => this.send());
    this.input.addEventListener('keydown', e => { if (e.key === 'Enter') this.send(); });
    document.querySelectorAll('.qr-btn').forEach(btn =>
      btn.addEventListener('click', () => { this.input.value = btn.dataset.msg; this.send(); })
    );
    $('clearBtn').addEventListener('click', async () => {
      await this._resetConversation();
    });
    $('minimizeBtn').addEventListener('click', () => this._setChatOpen(false));
    $('chatBubble').addEventListener('click', () => {
      this._setChatOpen(!this._isChatOpen());
    });
    $('cartBtn').addEventListener('click', () => this._showCart());
    $('exitSupportBtn').addEventListener('click', async () => {
      this.input.value = 'exit';
      await this.send();
    });
    // Language selector buttons
    document.querySelectorAll('.lang-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const lang = btn.dataset.lang;
        await i18n.load(lang);
        i18n.applyToDOM();
        this._updateLangBtns(lang);
        this._setSupportMode(this._inSupportMode); // re-apply placeholders
      });
    });
  }

  async _restoreAiState() {
    this._setSupportMode(false);
    try {
      const res = await fetch(`/api/support/requests/active/${encodeURIComponent(this.userId)}`);
      const data = await res.json();
      if (data.status === 'active') {
        await fetch('/api/session/reset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: this.userId })
        });
      }
    } catch (_) { }
    this._setSupportMode(false);
  }

  async _resetConversation() {
    const todayLabel = i18n.t('date_sep_today', 'Today');
    this.messages.innerHTML = `<div class="date-sep">${todayLabel}</div>`;
    this._setSupportMode(false);
    try {
      await fetch('/api/session/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: this.userId })
      });
    } catch (_) { }
    this._setSupportMode(false);
    await this._appendBotWithDelay(i18n.t('chat_cleared_msg', 'Chat cleared! How can I help you today? 😊'), 600, false);
  }

  _setSupportMode(on) {
    this._inSupportMode = on;
    const banner = $('supportBanner');
    const quickReplies = $('quickReplies');
    const input = this.input;
    if (on) {
      banner.classList.add('active');
      quickReplies.style.display = 'none';
      input.placeholder = i18n.t('input_placeholder_support', 'Type a message to the support agent...');
    } else {
      banner.classList.remove('active');
      SupportPoller.stop();
      quickReplies.style.display = '';
      input.placeholder = i18n.t('input_placeholder', 'Search products, track orders, ask anything...');
    }
  }

  async send() {
    const msg = this.input.value.trim();
    if (!msg) return;

    // Immediately leave support mode if exit command is sent, preventing race conditions with the poller
    const msgLower = msg.toLowerCase();
    if (this._inSupportMode && (msgLower === 'exit' || msgLower === 'reset' || msgLower === 'stop support')) {
      this._setSupportMode(false);
    }

    this._appendUser(msg);
    this.input.value = '';
    this.input.focus();
    this._setTyping(true);
    this.sendBtn.disabled = true;
    const started = Date.now();
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: this.userId, message: msg, lang: i18n.lang })
      });
      const data = await res.json();

      // Handle support mode
      if (data.in_support_mode) {
        this._setTyping(false);
        if (!this._inSupportMode) {
          this._setSupportMode(true);
          SupportPoller.start(this.userId, this);
          // Initial poll fills messages from the initial request
        }
        this.sendBtn.disabled = false;
        return;
      }

      if (data.intent === 'product_search') {
        this.lastProductQuery = msg;
        localStorage.setItem('gojo_last_product_query', msg);
      }

      // Exited support mode via 'exit' command
      if (this._inSupportMode && data.intent !== 'human_support') {
        this._setSupportMode(false);
      }

      const delay = data.typing_delay_ms || this._estimateDelay(data.response);
      const elapsed = Date.now() - started;
      const wait = Math.max(0, delay - elapsed);
      await this._sleep(wait);
      this._setTyping(false);
      await this._appendBotWithDelay(data.response, 0, true);
      this._refreshCartBadge();
    } catch (err) {
      this._setTyping(false);
      await this._appendBotWithDelay(i18n.t('connection_error', '⚠️ Connection error. Please try again.'), 500, false);
    } finally {
      this.sendBtn.disabled = false;
    }
  }

  _estimateDelay(text) {
    if (!text) return 800;
    if (text.includes('━━━')) return 1100;
    return Math.min(3200, 800 + text.split(/\s+/).length * 40);
  }

  _sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

  _appendUser(text) {
    const row = document.createElement('div');
    row.className = 'msg-row user';
    row.innerHTML = `
      <div class="bot-content">
        <div class="bubble">${this._esc(text)}</div>
        <div class="ts">${nowTime()}</div>
      </div>`;
    this.messages.appendChild(row);
    this._scroll();
  }

  _appendAgentMessage(text) {
    const row = document.createElement('div');
    row.className = 'msg-row agent';
    row.innerHTML = `
      <div class="bot-icon">👤</div>
      <div class="bot-content">
        <div class="agent-label">${i18n.t('support_agent_label', 'Support Agent')}</div>
        <div class="bubble">${this._esc(text)}</div>
        <div class="ts">${nowTime()}</div>
      </div>`;
    this.messages.appendChild(row);
    this._scroll();
    if (!this._isChatOpen()) {
      this._bumpUnread();
      this._playNotifySound();
    }
  }

  _appendBot(text) { return this._appendBotWithDelay(text, 0, false); }

  async _appendBotWithDelay(text, preDelay = 0, typewriter = false) {
    if (preDelay > 0) await this._sleep(preDelay);
    const row = document.createElement('div');
    const isProducts = isProductCard(text);
    const isSupport = isSupportCard(text);
    const isPromo = isPromoCard(text);
    const isCheckout = isCheckoutCard(text);
    const isCart = isCartCard(text);
    row.className = 'msg-row bot' + (isProducts || isPromo ? ' wide' : '');
    const useTypewriter = typewriter && !isProducts && !isOrderCard(text) && !isSupport && !isPromo && !isCheckout && !isCart;
    let inner = '';
    if (isSupport) {
      inner = renderSupportCard(parseSupportCard(text));
      // When support card is shown, activate live support mode
      setTimeout(() => {
        this._setSupportMode(true);
        SupportPoller.start(this.userId, this);
      }, 600);
    } else if (isCheckout) {
      inner = renderCheckoutCard(parseCheckoutCard(text));
    } else if (isCart) {
      inner = renderCartCard(parseCartCard(text));
    } else if (isOrderCard(text)) {
      inner = renderOrderCard(parseOrderCard(text));
    } else if (isPromo) {
      inner = renderPromoCard(parsePromoCard(text));
    } else if (isProducts) {
      inner = renderProductGrid(parseProductCard(text));
    } else {
      inner = `<div class="bubble">${useTypewriter ? '' : this._fmt(text)}</div>`;
    }
    row.innerHTML = `
      <div class="bot-icon">✦</div>
      <div class="bot-content">
        ${inner}
        <div class="ts">${nowTime()}</div>
      </div>`;
    this.messages.appendChild(row);
    this._scroll();
    if (useTypewriter) {
      const bubble = row.querySelector('.bubble');
      await this._typewriter(bubble, text);
    }
    if (!this._isChatOpen()) {
      this._bumpUnread();
      this._playNotifySound();
    }
  }

  async _typewriter(el, text) {
    let i = 0;
    const step = text.length > 280 ? 3 : text.length > 120 ? 2 : 1;
    const pause = text.length > 280 ? 12 : text.length > 120 ? 18 : 28;
    while (i < text.length) {
      el.innerHTML = this._fmt(text.slice(0, i + step));
      i += step; this._scroll();
      await this._sleep(pause);
    }
    el.innerHTML = this._fmt(text); this._scroll();
  }

  appendLocalBotMessage(text) { this._appendBot(text); }

  _setTyping(on) { this.typing.classList.toggle('active', on); this._scroll(); }

  _scroll() {
    requestAnimationFrame(() => { this.messages.scrollTop = this.messages.scrollHeight; });
  }

  _esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  _fmt(text) {
    const html = this._esc(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
    return linkifyCheckout(html);
  }
}

window.gojoChatInstance = new GojoChat();

window.applyProductFilter = (suffix) => {
  const chat = window.gojoChatInstance;
  chat.input.value = `${chat.lastProductQuery || 'products'}${suffix}`;
  chat.send();
};

window.showMoreProducts = () => {
  const chat = window.gojoChatInstance;
  chat.input.value = 'show more';
  chat.send();
};

window.addCartClicked = async (btn, id) => {
  const name = btn.dataset.productName || 'this item';
  btn.disabled = true;
  const originalHtml = btn.innerHTML;
  btn.innerHTML = i18n.t('cart_adding', 'Adding…');
  try {
    const res = await fetch('/api/cart/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: window.gojoChatInstance.userId, product: name })
    });
    if (res.ok) {
      btn.innerHTML = i18n.t('cart_added', '✓ Added');
      btn.style.background = 'var(--green)';
      window.gojoChatInstance._refreshCartBadge();
      setTimeout(() => {
        const cartMsg = i18n.t('cart_added_msg', '🛒 Added **{product}** to your cart! Type `checkout` when you\'re ready.').replace('{product}', name);
        window.gojoChatInstance.appendLocalBotMessage(cartMsg);
      }, 300);
    } else { throw new Error('Failed'); }
  } catch (err) {
    console.error(err);
    btn.innerHTML = i18n.t('cart_failed', 'Failed'); btn.style.background = 'var(--red)';
    setTimeout(() => { btn.innerHTML = originalHtml; btn.style.background = ''; btn.disabled = false; }, 1500);
  }
};

window.removeCartClicked = async (btn) => {
  const chat = window.gojoChatInstance;
  const name = btn.dataset.productName || '';
  if (!name) return;
  btn.disabled = true;
  const originalHtml = btn.innerHTML;
  btn.innerHTML = '…';
  try {
    const res = await fetch('/api/cart/remove', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: chat.userId, product: name })
    });
    if (!res.ok) throw new Error('Failed');
    await chat._refreshCartBadge();
    const details = await (await fetch(`/api/cart/details/${encodeURIComponent(chat.userId)}`)).json();
    const items = (details.items || []).map(it =>
      `${it.name} × ${it.quantity} — ${Number(it.subtotal || 0).toFixed(2)} ETB`);
    const total = `${Number(details.total_price || 0).toFixed(2)} ETB`;
    const card = btn.closest('.checkout-card');
    if (card) {
      const msg = i18n.t('cart_removed_msg', '✅ Removed {product} from your cart.').replace('{product}', name);
      const isCheckout = card.querySelector('.checkout-card-info');
      if (isCheckout && items.length > 0) {
        const rows = card.querySelectorAll('.checkout-row b');
        const nameVal = rows[0]?.textContent || '';
        const phoneVal = rows[1]?.textContent || '';
        const addressVal = rows[2]?.textContent || '';
        const paymentVal = rows[3]?.textContent || '';
        const promptVal = card.querySelector('.checkout-prompt')?.textContent || '';
        card.outerHTML = renderCheckoutCard({
          name: nameVal, phone: phoneVal, address: addressVal, payment: paymentVal,
          items, total, prompt: promptVal
        });
      } else {
        card.outerHTML = renderCartCard({ items, total, msg });
      }
    }
    chat._scroll();
  } catch (err) {
    console.error(err);
    btn.innerHTML = i18n.t('cart_failed', 'Failed');
    setTimeout(() => { btn.innerHTML = originalHtml; btn.disabled = false; }, 1500);
  }
};

window.clearCartClicked = async (btn) => {
  const chat = window.gojoChatInstance;
  btn.disabled = true;
  const originalHtml = btn.innerHTML;
  btn.innerHTML = '…';
  try {
    const res = await fetch('/api/cart/clear', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: chat.userId })
    });
    if (!res.ok) throw new Error('Failed');
    await chat._refreshCartBadge();
    const card = btn.closest('.checkout-card');
    if (card) {
      const msg = i18n.t('cart_cleared_msg', '🛒 Your cart has been cleared.');
      card.outerHTML = renderCartCard({ items: [], total: '0.00 ETB', msg });
    }
    chat._scroll();
  } catch (err) {
    console.error(err);
    btn.innerHTML = i18n.t('cart_failed', 'Failed');
    setTimeout(() => { btn.innerHTML = originalHtml; btn.disabled = false; }, 1500);
  }
};
