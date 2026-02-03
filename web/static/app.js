/* Polymarket Analyzer — SSE consumer & DOM rendering */

(function () {
  "use strict";

  const form = document.getElementById("analyze-form");
  const urlInput = document.getElementById("url-input");
  const analyzeBtn = document.getElementById("analyze-btn");
  const progressSection = document.getElementById("progress-section");
  const progressFill = document.getElementById("progress-fill");
  const progressMsg = document.getElementById("progress-msg");
  const errorSection = document.getElementById("error-section");
  const errorBox = document.getElementById("error-box");
  const resultsSection = document.getElementById("results-section");
  const marketCards = document.getElementById("market-cards");
  const summarySection = document.getElementById("summary-section");
  const summaryBox = document.getElementById("summary-box");

  // Watchlist elements
  const watchlistSidebar = document.getElementById("watchlist-sidebar");
  const watchlistToggle = document.getElementById("watchlist-toggle");
  const watchlistClose = document.getElementById("watchlist-close");
  const watchlistMinimize = document.getElementById("watchlist-minimize");
  const watchlistItems = document.getElementById("watchlist-items");
  const watchlistCount = document.getElementById("watchlist-count");

  let currentSource = null;

  /* ── Helpers ── */

  function show(el) { el.classList.remove("hidden"); }
  function hide(el) { el.classList.add("hidden"); }

  function fmt(n, decimals) {
    if (n == null) return "N/A";
    if (decimals === undefined) decimals = 0;
    return Number(n).toLocaleString("en-US", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  }

  function fmtUSD(n) {
    if (n == null) return "N/A";
    var prefix = n < 0 ? "-$" : "$";
    return prefix + fmt(Math.abs(n), 0);
  }

  function fmtPct(n) {
    if (n == null) return "N/A";
    return (n * 100).toFixed(1) + "%";
  }

  function shortAddr(addr) {
    if (!addr) return "";
    return addr.slice(0, 6) + "..." + addr.slice(-4);
  }

  function pnlClass(pnl) {
    if (pnl == null) return "unknown";
    return pnl > 0 ? "profitable" : "losing";
  }

  /* ── Watchlist Storage ── */

  const WATCHLIST_KEY = "polymarket_watchlist";

  function getWatchlist() {
    try {
      var data = localStorage.getItem(WATCHLIST_KEY);
      return data ? JSON.parse(data) : {};
    } catch (e) {
      return {};
    }
  }

  function saveWatchlist(watchlist) {
    try {
      localStorage.setItem(WATCHLIST_KEY, JSON.stringify(watchlist));
    } catch (e) {
      console.error("Failed to save watchlist:", e);
    }
  }

  function addToWatchlist(marketData) {
    var watchlist = getWatchlist();
    var key = marketData.market.condition_id;

    // Store market data with timestamp
    watchlist[key] = {
      market: marketData.market,
      scan_result: marketData.scan_result,
      yes_holders: marketData.yes_holders,
      no_holders: marketData.no_holders,
      savedAt: new Date().toISOString(),
      history: []  // Will store snapshots for change tracking
    };

    saveWatchlist(watchlist);
    updateWatchlistUI();
    return true;
  }

  function removeFromWatchlist(conditionId) {
    var watchlist = getWatchlist();
    delete watchlist[conditionId];
    saveWatchlist(watchlist);
    updateWatchlistUI();
  }

  function isInWatchlist(conditionId) {
    var watchlist = getWatchlist();
    return !!watchlist[conditionId];
  }

  function updateWatchlistWithNewData(conditionId, newData) {
    var watchlist = getWatchlist();
    if (!watchlist[conditionId]) return;

    var item = watchlist[conditionId];

    // Store previous state in history (keep last 10)
    if (item.scan_result) {
      item.history = item.history || [];
      item.history.unshift({
        timestamp: item.lastRefresh || item.savedAt,
        scan_result: item.scan_result,
        yes_price: item.scan_result.current_yes_price,
        no_price: item.scan_result.current_no_price,
        yes_profitable_pct: item.scan_result.yes_analysis.profitable_pct,
        no_profitable_pct: item.scan_result.no_analysis.profitable_pct
      });
      if (item.history.length > 10) {
        item.history = item.history.slice(0, 10);
      }
    }

    // Update with new data
    item.market = newData.market;
    item.scan_result = newData.scan_result;
    item.yes_holders = newData.yes_holders;
    item.no_holders = newData.no_holders;
    item.lastRefresh = new Date().toISOString();

    watchlist[conditionId] = item;
    saveWatchlist(watchlist);
    updateWatchlistUI();
  }

  /* ── Watchlist UI ── */

  function updateWatchlistUI() {
    var watchlist = getWatchlist();
    var keys = Object.keys(watchlist);

    // Update count badge
    if (keys.length > 0) {
      watchlistCount.textContent = keys.length;
      show(watchlistCount);
    } else {
      hide(watchlistCount);
    }

    // Update sidebar content
    if (keys.length === 0) {
      watchlistItems.innerHTML = '<p class="watchlist-empty">No markets saved yet. Click the bookmark icon on any market to add it.</p>';
      return;
    }

    // Build table-based watchlist
    var html = '<table class="watchlist-table">' +
      '<thead><tr>' +
        '<th>Signal</th>' +
        '<th>Market</th>' +
        '<th>Price</th>' +
        '<th>Change</th>' +
        '<th></th>' +
      '</tr></thead><tbody>';

    keys.forEach(function(key) {
      var item = watchlist[key];
      var sr = item.scan_result;
      var market = item.market;

      // Calculate changes if we have history
      var priceChange = '';
      var profChange = '';
      if (item.history && item.history.length > 0) {
        var prev = item.history[0];
        var yesPriceChange = sr.current_yes_price - prev.yes_price;
        var yesProfChange = sr.yes_analysis.profitable_pct - prev.yes_profitable_pct;

        if (Math.abs(yesPriceChange) > 0.001) {
          var priceChangeClass = yesPriceChange > 0 ? 'change-up' : 'change-down';
          var priceChangeSign = yesPriceChange > 0 ? '+' : '';
          priceChange = '<span class="change-pill ' + priceChangeClass + '">' + priceChangeSign + (yesPriceChange * 100).toFixed(1) + '%</span>';
        }
        if (Math.abs(yesProfChange) > 0.001) {
          var profChangeClass = yesProfChange > 0 ? 'change-up' : 'change-down';
          var profChangeSign = yesProfChange > 0 ? '+' : '';
          profChange = '<span class="change-pill ' + profChangeClass + '" title="Profitable % change">' + profChangeSign + (yesProfChange * 100).toFixed(1) + '</span>';
        }
      }

      var verdictClass = sr.is_flagged ? (sr.flagged_side === 'YES' ? 'verdict-yes' : 'verdict-no') : 'verdict-neutral';
      var verdictText = sr.is_flagged ? sr.flagged_side : '—';

      // Truncate question for table
      var shortQuestion = sr.question.length > 50 ? sr.question.substring(0, 47) + '...' : sr.question;

      html += '<tr class="watchlist-row" data-condition-id="' + key + '">' +
        '<td><span class="verdict-sm ' + verdictClass + '">' + verdictText + '</span></td>' +
        '<td class="market-cell" title="' + escapeHtml(sr.question) + '">' + escapeHtml(shortQuestion) + '</td>' +
        '<td class="price-cell"><span class="price-yes-sm">' + (sr.current_yes_price * 100).toFixed(0) + '¢</span></td>' +
        '<td class="change-cell">' + (priceChange || profChange || '<span class="no-change">—</span>') + '</td>' +
        '<td class="actions-cell">' +
          '<button class="watchlist-refresh-sm" data-condition-id="' + key + '" data-slug="' + escapeHtml(market.slug) + '" title="Refresh">↻</button>' +
          '<button class="watchlist-remove-sm" data-condition-id="' + key + '" title="Remove">×</button>' +
        '</td>' +
      '</tr>';
    });

    html += '</tbody></table>';
    watchlistItems.innerHTML = html;
  }

  function formatTimeAgo(isoString) {
    var date = new Date(isoString);
    var now = new Date();
    var diffMs = now - date;
    var diffMins = Math.floor(diffMs / 60000);
    var diffHours = Math.floor(diffMins / 60);
    var diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return diffMins + 'm ago';
    if (diffHours < 24) return diffHours + 'h ago';
    return diffDays + 'd ago';
  }

  /* ── Watchlist Events ── */

  watchlistToggle.addEventListener("click", function() {
    watchlistSidebar.classList.add("open");
    watchlistSidebar.classList.remove("minimized");
  });

  watchlistClose.addEventListener("click", function() {
    watchlistSidebar.classList.remove("open");
    watchlistSidebar.classList.remove("minimized");
  });

  watchlistMinimize.addEventListener("click", function() {
    var isMinimized = watchlistSidebar.classList.toggle("minimized");
    watchlistMinimize.textContent = isMinimized ? "+" : "−";
    watchlistMinimize.title = isMinimized ? "Expand" : "Minimize";
  });

  // Handle clicks within watchlist
  watchlistItems.addEventListener("click", function(e) {
    // Remove button
    var removeBtn = e.target.closest(".watchlist-remove-sm");
    if (removeBtn) {
      e.stopPropagation();
      var conditionId = removeBtn.getAttribute("data-condition-id");
      removeFromWatchlist(conditionId);
      return;
    }

    // Refresh button
    var refreshBtn = e.target.closest(".watchlist-refresh-sm");
    if (refreshBtn) {
      e.stopPropagation();
      var conditionId = refreshBtn.getAttribute("data-condition-id");
      var slug = refreshBtn.getAttribute("data-slug");
      refreshWatchlistItem(conditionId, slug, refreshBtn);
      return;
    }

    // Click on row to analyze
    var row = e.target.closest(".watchlist-row");
    if (row && !e.target.closest("button")) {
      var conditionId = row.getAttribute("data-condition-id");
      var watchlist = getWatchlist();
      var data = watchlist[conditionId];
      if (data && data.market && data.market.slug) {
        urlInput.value = "https://polymarket.com/event/" + data.market.slug;
        watchlistSidebar.classList.remove("open");
        startAnalysis(urlInput.value);
      }
    }
  });

  function refreshWatchlistItem(conditionId, slug, btn) {
    btn.disabled = true;
    btn.textContent = "...";
    btn.classList.add("loading");

    var url = "https://polymarket.com/event/" + slug;
    var source = new EventSource("/api/analyze?url=" + encodeURIComponent(url));

    source.addEventListener("market_result", function(e) {
      var d = JSON.parse(e.data);
      updateWatchlistWithNewData(conditionId, d);
      source.close();
      btn.disabled = false;
      btn.textContent = "↻";
      btn.classList.remove("loading");
    });

    source.addEventListener("error", function() {
      source.close();
      btn.disabled = false;
      btn.textContent = "↻";
      btn.classList.remove("loading");
    });

    source.addEventListener("complete", function() {
      source.close();
      btn.disabled = false;
      btn.textContent = "↻";
      btn.classList.remove("loading");
    });
  }

  /* ── Reset UI ── */

  function resetUI() {
    hide(progressSection);
    hide(errorSection);
    hide(summarySection);
    hide(resultsSection);
    marketCards.innerHTML = "";
    errorBox.textContent = "";
    progressFill.style.width = "0%";
  }

  /* ── Render a market card ── */

  function renderMarketCard(data) {
    var sr = data.scan_result;
    var market = data.market;
    var yesA = sr.yes_analysis;
    var noA = sr.no_analysis;

    var card = document.createElement("div");
    card.className = "market-card";
    card.setAttribute("data-condition-id", market.condition_id);

    // Check if in watchlist
    var inWatchlist = isInWatchlist(market.condition_id);
    var bookmarkClass = inWatchlist ? "bookmark-btn active" : "bookmark-btn";
    var bookmarkTitle = inWatchlist ? "Remove from watchlist" : "Add to watchlist";

    // Verdict
    var verdictClass, verdictText;
    if (sr.is_flagged) {
      verdictClass = sr.flagged_side === "YES" ? "verdict-yes" : "verdict-no";
      verdictText = "FLAGGED " + sr.flagged_side + "  (score: " + sr.imbalance_score.toFixed(0) + ")";
    } else {
      verdictClass = "verdict-neutral";
      verdictText = "NO SIGNAL";
    }

    // Build header with bookmark button in meta row
    var bookmarkText = inWatchlist ? 'Saved' : 'Save';
    var headerHTML =
      '<div class="card-header">' +
        '<h2 class="card-question">' + escapeHtml(sr.question) + '</h2>' +
        '<div class="card-meta">' +
          '<span class="verdict ' + verdictClass + '">' + verdictText + '</span>' +
          '<a class="pm-link" href="https://polymarket.com/event/' + encodeURIComponent(market.slug) + '" target="_blank" rel="noopener">View on Polymarket</a>' +
          '<button class="' + bookmarkClass + '" title="' + bookmarkTitle + '" data-condition-id="' + market.condition_id + '">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="' + (inWatchlist ? 'currentColor' : 'none') + '" stroke="currentColor" stroke-width="2">' +
              '<path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>' +
            '</svg>' +
            '<span class="bookmark-text">' + bookmarkText + '</span>' +
          '</button>' +
        '</div>' +
      '</div>';

    // Price bar
    var yesPct = (sr.current_yes_price * 100).toFixed(0);
    var noPct = (sr.current_no_price * 100).toFixed(0);
    var priceBarHTML =
      '<div class="price-bar">' +
        '<div class="price-yes" style="width:' + yesPct + '%">' + yesPct + '% YES</div>' +
        '<div class="price-no" style="width:' + noPct + '%">' + noPct + '% NO</div>' +
      '</div>';

    // Profitability comparison bar
    var yesProf = (yesA.profitable_pct * 100).toFixed(0);
    var noProf = (noA.profitable_pct * 100).toFixed(0);
    var profBarHTML =
      '<div class="section-label">Profitable Trader %</div>' +
      '<div class="prof-bar">' +
        '<div class="prof-yes' + (yesA.profitable_pct >= 0.6 ? " above-threshold" : "") + '" style="width:' + Math.max(yesProf, 5) + '%">' + yesProf + '% YES</div>' +
        '<div class="prof-no' + (noA.profitable_pct >= 0.6 ? " above-threshold" : "") + '" style="width:' + Math.max(noProf, 5) + '%">' + noProf + '% NO</div>' +
      '</div>' +
      '<div class="threshold-note">Flag threshold: 60%</div>';

    // Side panels
    var panelsHTML =
      '<div class="side-panels">' +
        renderSidePanel(yesA, "yes") +
        renderSidePanel(noA, "no") +
      '</div>';

    // Data quality
    var avgQuality = ((yesA.data_quality_score + noA.data_quality_score) / 2).toFixed(0);
    var qualityClass = avgQuality >= 70 ? "quality-good" : avgQuality >= 40 ? "quality-ok" : "quality-low";
    var qualityHTML =
      '<div class="data-quality ' + qualityClass + '">Data Quality: ' + avgQuality + '/100</div>';

    // Market stats
    var statsHTML =
      '<div class="market-stats">' +
        '<span>Vol: $' + fmt(market.volume) + '</span>' +
        '<span>Liq: $' + fmt(market.liquidity) + '</span>' +
      '</div>';

    // Holder tables (collapsible)
    var holdersHTML =
      renderHolderTable(data.yes_holders, "YES", data.index) +
      renderHolderTable(data.no_holders, "NO", data.index);

    card.innerHTML = headerHTML + priceBarHTML + profBarHTML + panelsHTML + qualityHTML + statsHTML + holdersHTML;

    // Store the full data on the card element for watchlist
    card._marketData = data;

    marketCards.appendChild(card);
    show(resultsSection);
  }

  function renderSidePanel(analysis, side) {
    var sideLabel = side.toUpperCase();
    var known = analysis.profitable_count + analysis.losing_count;
    return (
      '<div class="side-panel side-' + side + '">' +
        '<h3>' + sideLabel + ' Side</h3>' +
        '<div class="stat-row"><span class="stat-label">Holders analyzed</span><span class="stat-value">' + analysis.top_n_count + '</span></div>' +
        '<div class="stat-row"><span class="stat-label">Profitable (account)</span><span class="stat-value">' + analysis.profitable_count + ' / ' + known + ' (' + fmtPct(analysis.profitable_pct) + ')</span></div>' +
        '<div class="stat-row"><span class="stat-label">Unknown</span><span class="stat-value">' + analysis.unknown_count + '</span></div>' +
        '<div class="stat-row"><span class="stat-label">Avg Market PNL</span><span class="stat-value ' + pnlClass(analysis.avg_overall_pnl) + '">' + fmtUSD(analysis.avg_overall_pnl) + '</span></div>' +
        '<div class="stat-row"><span class="stat-label">Avg Account PNL</span><span class="stat-value ' + pnlClass(analysis.avg_realized_pnl) + '">' + fmtUSD(analysis.avg_realized_pnl) + '</span></div>' +
        '<div class="stat-row"><span class="stat-label">Position size</span><span class="stat-value">' + fmt(analysis.total_position_size, 0) + ' shares</span></div>' +
      '</div>'
    );
  }

  function renderHolderTable(holders, sideLabel, cardIndex) {
    if (!holders || holders.length === 0) {
      return '<div class="holder-section"><h4>' + sideLabel + ' Holders</h4><p class="no-data">No holders found</p></div>';
    }
    var id = "holders-" + sideLabel.toLowerCase() + "-" + cardIndex;
    var html =
      '<div class="holder-section">' +
        '<h4 class="collapsible-toggle" data-target="' + id + '">' +
          sideLabel + ' Holders (' + holders.length + ') <span class="toggle-icon">+</span>' +
        '</h4>' +
        '<div id="' + id + '" class="collapsible hidden">' +
          '<table class="holder-table">' +
            '<thead><tr><th>Wallet</th><th>Amount</th><th>Market PNL</th><th>Account PNL</th><th>Status</th></tr></thead>' +
            '<tbody>';

    for (var i = 0; i < holders.length; i++) {
      var h = holders[i];
      // Market PNL = unrealized P&L on this specific position
      var marketPnlClass = pnlClass(h.overall_pnl);
      // Account PNL = lifetime realized P&L (determines profitable/losing status)
      var accountPnlClass = pnlClass(h.realized_pnl);
      var status = h.realized_pnl != null ? (h.realized_pnl > 0 ? "Profitable" : "Losing") : "Unknown";
      html +=
        '<tr class="' + accountPnlClass + '">' +
          '<td class="wallet">' + (h.username || shortAddr(h.wallet_address)) + '</td>' +
          '<td>' + fmt(h.amount, 0) + '</td>' +
          '<td class="' + marketPnlClass + '">' + fmtUSD(h.overall_pnl) + '</td>' +
          '<td class="' + accountPnlClass + '">' + fmtUSD(h.realized_pnl) + '</td>' +
          '<td>' + status + '</td>' +
        '</tr>';
    }

    html += '</tbody></table></div></div>';
    return html;
  }

  function escapeHtml(text) {
    var div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  /* ── Collapsible sections & Bookmark (event delegation) ── */

  document.addEventListener("click", function (e) {
    // Collapsible toggle
    var toggle = e.target.closest(".collapsible-toggle");
    if (toggle) {
      var targetId = toggle.getAttribute("data-target");
      var target = document.getElementById(targetId);
      if (!target) return;
      var icon = toggle.querySelector(".toggle-icon");
      if (target.classList.contains("hidden")) {
        target.classList.remove("hidden");
        if (icon) icon.textContent = "\u2212";
      } else {
        target.classList.add("hidden");
        if (icon) icon.textContent = "+";
      }
      return;
    }

    // Bookmark button
    var bookmarkBtn = e.target.closest(".bookmark-btn");
    if (bookmarkBtn) {
      var conditionId = bookmarkBtn.getAttribute("data-condition-id");
      var card = bookmarkBtn.closest(".market-card");
      var textSpan = bookmarkBtn.querySelector(".bookmark-text");

      if (isInWatchlist(conditionId)) {
        removeFromWatchlist(conditionId);
        bookmarkBtn.classList.remove("active");
        bookmarkBtn.title = "Add to watchlist";
        bookmarkBtn.querySelector("svg").setAttribute("fill", "none");
        if (textSpan) textSpan.textContent = "Save";
      } else if (card && card._marketData) {
        addToWatchlist(card._marketData);
        bookmarkBtn.classList.add("active");
        bookmarkBtn.title = "Remove from watchlist";
        bookmarkBtn.querySelector("svg").setAttribute("fill", "currentColor");
        if (textSpan) textSpan.textContent = "Saved";
      }
      return;
    }
  });

  /* ── SSE connection ── */

  function startAnalysis(url) {
    if (currentSource) {
      currentSource.close();
      currentSource = null;
    }
    resetUI();
    show(progressSection);
    progressMsg.textContent = "Connecting...";
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Analyzing...";

    // Update browser URL for shareability
    try {
      var parsed = url.match(/polymarket\.com\/event\/(.+)/);
      if (parsed) {
        history.pushState(null, "", "/analyze/" + parsed[1]);
      }
    } catch (_) { /* ignore */ }

    var source = new EventSource("/api/analyze?url=" + encodeURIComponent(url));
    currentSource = source;

    source.addEventListener("progress", function (e) {
      var d = JSON.parse(e.data);
      progressMsg.textContent = d.message;
      if (d.total > 0) {
        var pct = Math.round((d.current / d.total) * 100);
        progressFill.style.width = pct + "%";
      }
    });

    source.addEventListener("market_result", function (e) {
      var d = JSON.parse(e.data);
      renderMarketCard(d);

      // If this market is in watchlist, update it with fresh data
      if (isInWatchlist(d.market.condition_id)) {
        updateWatchlistWithNewData(d.market.condition_id, d);
      }

      // Update progress
      if (d.total > 0) {
        var pct = Math.round(((d.index + 1) / d.total) * 100);
        progressFill.style.width = pct + "%";
        progressMsg.textContent = "Analyzed " + (d.index + 1) + " / " + d.total + " markets";
      }
    });

    source.addEventListener("error", function (e) {
      // SSE spec calls this for connection errors AND custom error events
      if (e.data) {
        var d = JSON.parse(e.data);
        show(errorSection);
        errorBox.textContent = d.message;
      }
    });

    source.addEventListener("complete", function (e) {
      var d = JSON.parse(e.data);
      source.close();
      currentSource = null;
      progressFill.style.width = "100%";
      hide(progressSection);
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "Analyze";

      // Show summary
      show(summarySection);
      summaryBox.innerHTML =
        '<strong>Analysis Complete</strong> &mdash; ' +
        d.completed + ' market(s) analyzed, ' +
        d.flagged + ' flagged | ' +
        d.cached_wallets + ' wallets checked (' + d.api_calls + ' API calls)';
    });

    source.onerror = function () {
      // Connection-level error (not a custom error event)
      if (source.readyState === EventSource.CLOSED) {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "Analyze";
        hide(progressSection);
      }
    };
  }

  /* ── Form submit ── */

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var url = urlInput.value.trim();
    if (!url) return;
    startAnalysis(url);
  });

  /* ── Initialize ── */

  // Load watchlist on startup
  updateWatchlistUI();

  /* ── Prefill from shareable URL ── */

  if (window.__PREFILL_URL__) {
    urlInput.value = window.__PREFILL_URL__;
    startAnalysis(window.__PREFILL_URL__);
  }
})();
