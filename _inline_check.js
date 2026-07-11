
const $ = id => document.getElementById(id);

const PRODUCT_IMAGE_BASE = 'https://gojoshop.et/storage/product/thumbnail/';

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

  function parseProducts(block) {
    const sections = block.split('\n---');
    const parsed = [];

    for (const sec of sections) {
      const lines = sec.split('\n');
      const prod = {};
      for (const line of lines) {
        const t = line.trim();
        if (!t || t.startsWith('Filters:') || t.includes('PRODUCT SEARCH')) continue;
        if (t.startsWith('Product ID:')) { prod.id = t.replace('Product ID:', '').trim(); continue; }
        if (t.startsWith('Name:'))       { prod.name = t.replace('Name:', '').trim(); continue; }
        if (t.startsWith('Price:'))      { prod.price = t.replace('Price:', '').trim(); continue; }
        if (t.startsWith('Stock:'))      { prod.stock = t.replace('Stock:', '').trim(); continue; }
        if (t.startsWith('Image:'))      { prod.image = t.replace('Image:', '').trim(); continue; }
        if (t.startsWith('Details:'))    { prod.details = t.replace('Details:', '').trim(); continue; }
      }
      if (prod.id && prod.name) parsed.push(prod);
    }
    return parsed;
  }

  return {
    products: parseProducts(resultText),
    recommendations: parseProducts(recText),
    filters: filtersLine ? filtersLine.replace('Filters:', '').trim() : 'none',
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
    toy:      'https://images.unsplash.com/photo-1559251606-c623743a6d76?auto=format&fit=crop&w=400&q=80',
    bear:     'https://images.unsplash.com/photo-1582060047814-1237a2f2a75d?auto=format&fit=crop&w=400&q=80',
    monkey:   'https://images.unsplash.com/photo-1540573133985-87b6da6d54a9?auto=format&fit=crop&w=400&q=80',
    hippo:    'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?auto=format&fit=crop&w=400&q=80',
    earring:  'https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=400&q=80',
    bag:      'https://images.unsplash.com/photo-1584917865442-de89df76afd3?auto=format&fit=crop&w=400&q=80',
    backpack: 'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=400&q=80',
    purse:    'https://images.unsplash.com/photo-1566150905458-1bf1fc15a7a5?auto=format&fit=crop&w=400&q=80',
    shoe:     'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=400&q=80',
    dress:    'https://images.unsplash.com/photo-1595777457583-95e059d581b8?auto=format&fit=crop&w=400&q=80',
    shirt:    'https://images.unsplash.com/photo-1521572267360-ee0c2909d518?auto=format&fit=crop&w=400&q=80',
    towel:    'https://images.unsplash.com/photo-1563453392212-326f5e854473?auto=format&fit=crop&w=400&q=80',
    coaster:  'https://images.unsplash.com/photo-1616486338812-3dadae4b4ace?auto=format&fit=crop&w=400&q=80',
    product:  'https://images.unsplash.com/photo-1472851294608-062f824d29cc?auto=format&fit=crop&w=400&q=80'
  };
  return images[foundKeyword];
}

function resolveProductImage(thumbnail, name) {
  if (thumbnail && thumbnail.startsWith('http')) return thumbnail;
  if (thumbnail && thumbnail !== 'def.png') return PRODUCT_IMAGE_BASE + thumbnail;
  return getProductImage(name);
}

const cartIcon = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/><path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"/></svg>`;

function renderProductCards(products) {
  return products.map(p => {
    const isOutOfStock = parseInt(p.stock) <= 0;
    const stockClass = isOutOfStock ? 'stock-out' : 'stock-available';
    const stockText = isOutOfStock ? 'Out of stock' : `${p.stock} in stock`;
    const imgUrl = resolveProductImage(p.image, p.name);
    const safeName = escHtml(p.name);
    const safeDetails = escHtml(p.details);
    const safeImage = escHtml(imgUrl);
    const safePrice = escHtml(p.price);
    const safeStockText = escHtml(stockText);
    const productId = Number.parseInt(p.id, 10);
    const desc = safeDetails ? `<p class="product-desc">${safeDetails}</p>` : '';

    return `
      <div class="product-card">
        <div class="product-img" style="background-image:url('${safeImage}')">
          <div class="product-price-badge">${safePrice}</div>
        </div>
        <div class="product-info">
          <h3 class="product-title" title="${safeName}">${safeName}</h3>
          ${desc}
          <span class="product-stock ${stockClass}"><span class="stock-dot"></span>${safeStockText}</span>
          <button
            class="add-cart-btn"
            data-product-name="${safeName}"
            onclick="addCartClicked(this, ${productId})"
            ${isOutOfStock ? 'disabled' : ''}
          >
            ${isOutOfStock ? 'Sold Out' : cartIcon + ' Add'}
          </button>
        </div>
      </div>`;
  }).join('');
}

function formatFilters(filters) {
  if (!filters || filters === 'none') return 'No filters applied';
  return filters
    .replace(/min_price=/g, 'Min ')
    .replace(/max_price=/g, 'Max ')
    .replace(/in_stock=true/g, 'In stock')
    .replace(/sort=price_asc/g, 'Cheapest first')
    .replace(/sort=price_desc/g, 'Highest price first')
    .replace(/sort=newest/g, 'Newest first')
    .replace(/;/g, ' · ');
}

function renderProductGrid(data) {
  const products = data.products || [];
  const recommendations = data.recommendations || [];
  const cards = renderProductCards(products);
  const recCards = renderProductCards(recommendations);
  const count = products.length;
  const label = count === 1 ? '1 product' : `${count} products`;
  const activeFilters = formatFilters(data.filters);
  const filterButtons = [
    ['In stock', ' in stock'],
    ['Cheapest', ' cheapest'],
    ['Newest', ' newest'],
    ['Under 1000', ' under 1000'],
  ].map(([labelText, suffix]) =>
    `<button class="filter-btn" onclick="applyProductFilter('${suffix}')">${labelText}</button>`
  ).join('');
  const recSection = recommendations.length
    ? `<div class="recommendation-section"><div class="recommendation-title">Recommended alternatives</div><div class="product-track">${recCards}</div></div>`
    : '';

  return `
    <div class="product-results">
      <div class="product-results-header">
        <h3>Search Results</h3>
        <span class="product-count">${label}</span>
      </div>
      <div class="product-filter-bar">${filterButtons}</div>
      <div class="active-filters">${escHtml(activeFilters)}</div>
      <div class="product-track">${cards}</div>
      ${recSection}
    </div>`;
}

/* Order card renderer */
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
    if (t.startsWith('Shop:'))   data.shop   = t.replace('Shop:', '').trim();
    if (t.startsWith('Email:'))  data.email  = t.replace('Email:', '').trim();
    if (t.startsWith('Phone:'))  data.phone  = t.replace('Phone:', '').trim();
    if (t.startsWith('Hours:'))  data.hours  = t.replace('Hours:', '').trim();
    if (t.startsWith('Note:'))   data.note   = t.replace('Note:', '').trim();
  }
  return data;
}

function renderSupportCard(data) {
  const intro = data.intro
    ? `<p class="support-intro">${data.intro.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>')}</p>`
    : '';
  const email = data.email || 'support@gojoshop.et';
  const phone = (data.phone || '+251911234567').replace(/\s/g, '');
  return `
    <div class="support-card">
      ${intro}
      <div class="support-card-header">
        <span class="support-badge">💬 Human Support</span>
        <span class="support-shop">${data.shop || 'GojoShop.et'}</span>
      </div>
      <div class="support-actions">
        <a class="support-btn email" href="mailto:${email}">📧 Email us</a>
        <a class="support-btn phone" href="tel:${phone}">📞 Call us</a>
      </div>
      <div class="support-meta">
        <div><strong>Email</strong><span>${email}</span></div>
        <div><strong>Phone</strong><span>${data.phone || phone}</span></div>
        <div><strong>Hours</strong><span>${data.hours || 'Mon–Sat, 9–6 EAT'}</span></div>
      </div>
      ${data.note ? `<p class="support-note">${data.note}</p>` : ''}
    </div>`;
}

function isOrderCard(text) {
  return text.startsWith('━━━') && !text.includes('PRODUCT SEARCH') && !isSupportCard(text);
}

const STATUS_CLASS = {
  DELIVERED:  'status-delivered',
  SHIPPED:    'status-shipped',
  PROCESSING: 'status-processing',
  PENDING:    'status-pending',
  CANCELLED:  'status-cancelled',
};
const STATUS_EMOJI = {
  DELIVERED:'✅', SHIPPED:'🚚', PROCESSING:'⚙️', PENDING:'🕒', CANCELLED:'✖️'
};

function parseOrderCard(text) {
  const lines = text.split('\n').filter(l => !l.startsWith('━━━'));
  const data = {};
  const items = [];
  let inItems = false;

  for (const line of lines) {
    const t = line.trim();
    if (!t) continue;
    if (t.startsWith('🧾 Order:'))       { data.order_id   = t.replace('🧾 Order:', '').trim(); continue; }
    if (t.startsWith('👤'))             { data.customer   = t.replace('👤','').trim(); continue; }
    if (t.startsWith('🗓️ Placed:'))     { data.placed     = t.replace('🗓️ Placed:','').trim(); continue; }
    if (t.startsWith('Status:'))       { data.status     = t.replace(/Status:.*?(\w+)$/,'$1').trim().toUpperCase(); continue; }
    if (t.startsWith('Tracking:'))     { data.tracking   = t.replace('Tracking:','').trim(); continue; }
    if (t.startsWith('Delivery to:'))  { data.address    = t.replace('Delivery to:','').trim(); continue; }
    if (t.startsWith('🛍️ Items:'))      { inItems = true;  continue; }
    if (t.startsWith('💳 Payment:'))   { inItems = false; data.payment = t.replace('💳 Payment:','').trim(); continue; }
    if (t.startsWith('💰 Total:'))     { data.total      = t.replace('💰 Total:','').trim(); continue; }
    if (inItems && t.startsWith('•')) {
      const m = t.match(/•\s(.+?)\s×\s(\d+)\s+—\s+(.+)/);
      if (m) items.push({ name: m[1], qty: m[2], price: m[3] });
      continue;
    }
    if (!t.startsWith('•') && !inItems && data.total) data.statusMsg = t;
  }
  data.items = items;
  return data;
}

function renderOrderCard(data) {
  const sc = STATUS_CLASS[data.status] || 'status-pending';
  const se = STATUS_EMOJI[data.status] || '📦';
  const itemRows = data.items.map(it =>
    `<li><span>${it.name} × ${it.qty}</span><span>${it.price}</span></li>`
  ).join('');

  return `
    <div class="order-card">
      <div class="oc-row"><span class="oc-label">Order ID</span><span class="oc-val">${data.order_id || '—'}</span></div>
      <div class="oc-row"><span class="oc-label">Customer</span><span class="oc-val">${data.customer || '—'}</span></div>
      <div class="oc-row"><span class="oc-label">Placed</span><span class="oc-val">${data.placed || '—'}</span></div>
      <hr class="oc-divider"/>
      <div class="oc-row"><span class="oc-label">Status</span><span class="status-badge ${sc}">${se} ${data.status || '—'}</span></div>
      <div class="oc-row"><span class="oc-label">Tracking</span><span class="oc-val">${data.tracking || '—'}</span></div>
      <div class="oc-row"><span class="oc-label">Delivery</span><span class="oc-val">${data.address || '—'}</span></div>
      <hr class="oc-divider"/>
      <ul class="oc-items-list">${itemRows}</ul>
      <hr class="oc-divider"/>
      <div class="oc-row"><span class="oc-label">Payment</span><span class="oc-val">${data.payment || '—'}</span></div>
      <div class="oc-row"><span class="oc-label">Total</span><span class="oc-val oc-total">${data.total || '—'}</span></div>
      ${data.statusMsg ? `<hr class="oc-divider"/><div style="font-size:12.5px;color:var(--text-muted)">${data.statusMsg}</div>` : ''}
    </div>`;
}

/* Chat client */
class GojoChat {
  constructor() {
    this.userId   = localStorage.getItem('gojo_uid') || this._genId();
    localStorage.setItem('gojo_uid', this.userId);

    this.input    = $('msgInput');
    this.sendBtn  = $('sendBtn');
    this.messages = $('chatMessages');
    this.typing   = $('typingRow');
    this.lastProductQuery = localStorage.getItem('gojo_last_product_query') || '';

    $('welcomeTs').textContent = nowTime();
    this._bind();
  }

  _genId() { return 'u_' + Date.now() + '_' + Math.random().toString(36).slice(2, 9); }

  _bind() {
    this.sendBtn.addEventListener('click', () => this.send());
    this.input.addEventListener('keydown', e => { if (e.key === 'Enter') this.send(); });
    document.querySelectorAll('.qr-btn').forEach(btn =>
      btn.addEventListener('click', () => {
        this.input.value = btn.dataset.msg;
        this.send();
      })
    );
    $('clearBtn').addEventListener('click', async () => {
      this.messages.innerHTML = '<div class="date-sep">Today</div>';
      try {
        await fetch('/api/session/reset', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: this.userId })
        });
      } catch (_) {}
      await this._appendBotWithDelay('Chat cleared! How can I help you today? 😊', 600, false);
    });
  }

  async send() {
    const msg = this.input.value.trim();
    if (!msg) return;

    this._appendUser(msg);
    this.input.value = '';
    this.input.focus();
    this._setTyping(true);
    this.sendBtn.disabled = true;

    const started = Date.now();

    try {
      const res  = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: this.userId, message: msg })
      });
      const data = await res.json();
      if (data.intent === 'product_search') {
        this.lastProductQuery = msg;
        localStorage.setItem('gojo_last_product_query', msg);
      }
      const delay = data.typing_delay_ms || this._estimateDelay(data.response);
      const elapsed = Date.now() - started;
      const wait = Math.max(0, delay - elapsed);
      await this._sleep(wait);
      this._setTyping(false);
      await this._appendBotWithDelay(data.response, 0, true);
    } catch (err) {
      this._setTyping(false);
      await this._appendBotWithDelay('⚠️ Connection error. Please try again.', 500, false);
    } finally {
      this.sendBtn.disabled = false;
    }
  }

  _estimateDelay(text) {
    if (!text) return 800;
    if (text.includes('━━━')) return 1100;
    return Math.min(3200, 800 + text.split(/\s+/).length * 40);
  }

  _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

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

  _appendBot(text) {
    return this._appendBotWithDelay(text, 0, false);
  }

  async _appendBotWithDelay(text, preDelay = 0, typewriter = false) {
    if (preDelay > 0) await this._sleep(preDelay);

    const row = document.createElement('div');
    const isProducts = isProductCard(text);
    const isSupport = isSupportCard(text);
    row.className = 'msg-row bot' + (isProducts ? ' wide' : '');

    const useTypewriter = typewriter && !isProducts && !isOrderCard(text) && !isSupport;

    let inner = '';
    if (isSupport) {
      inner = renderSupportCard(parseSupportCard(text));
    } else if (isOrderCard(text)) {
      inner = renderOrderCard(parseOrderCard(text));
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
  }

  async _typewriter(el, text) {
    const plain = text;
    let i = 0;
    const step = plain.length > 280 ? 3 : plain.length > 120 ? 2 : 1;
    const pause = plain.length > 280 ? 12 : plain.length > 120 ? 18 : 28;

    while (i < plain.length) {
      const chunk = plain.slice(0, i + step);
      el.innerHTML = this._fmt(chunk);
      i += step;
      this._scroll();
      await this._sleep(pause);
    }
    el.innerHTML = this._fmt(plain);
    this._scroll();
  }

  appendLocalBotMessage(text) {
    this._appendBot(text);
  }

  _setTyping(on) {
    this.typing.classList.toggle('active', on);
    this._scroll();
  }

  _scroll() {
    requestAnimationFrame(() => {
      this.messages.scrollTop = this.messages.scrollHeight;
    });
  }

  _esc(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  _fmt(text) {
    return this._esc(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  }
}

window.gojoChatInstance = new GojoChat();

window.applyProductFilter = (suffix) => {
  const chat = window.gojoChatInstance;
  const base = chat.lastProductQuery || 'products';
  chat.input.value = `${base}${suffix}`;
  chat.send();
};

window.addCartClicked = async (btn, id) => {
  const name = btn.dataset.productName || 'this item';
  btn.disabled = true;
  const originalHtml = btn.innerHTML;
  btn.innerHTML = 'Adding…';

  try {
    const res = await fetch('/api/cart/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: window.gojoChatInstance.userId, product: name })
    });

    if (res.ok) {
      btn.innerHTML = '✓ Added';
      btn.style.background = 'var(--green)';
      setTimeout(() => {
        window.gojoChatInstance.appendLocalBotMessage(`🛒 Added **${name}** to your cart! Type \`checkout\` when you're ready.`);
      }, 300);
    } else {
      throw new Error('Failed to add');
    }
  } catch (err) {
    console.error(err);
    btn.innerHTML = 'Failed';
    btn.style.background = 'var(--red)';
    setTimeout(() => {
      btn.innerHTML = originalHtml;
      btn.style.background = '';
      btn.disabled = false;
    }, 1500);
  }
};

