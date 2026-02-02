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

    // Verdict
    var verdictClass, verdictText;
    if (sr.is_flagged) {
      verdictClass = sr.flagged_side === "YES" ? "verdict-yes" : "verdict-no";
      verdictText = "FLAGGED " + sr.flagged_side + "  (score: " + sr.imbalance_score.toFixed(0) + ")";
    } else {
      verdictClass = "verdict-neutral";
      verdictText = "NO SIGNAL";
    }

    // Build header
    var headerHTML =
      '<div class="card-header">' +
        '<h2 class="card-question">' + escapeHtml(sr.question) + '</h2>' +
        '<div class="card-meta">' +
          '<span class="verdict ' + verdictClass + '">' + verdictText + '</span>' +
          '<a class="pm-link" href="https://polymarket.com/event/' + encodeURIComponent(market.slug) + '" target="_blank" rel="noopener">View on Polymarket</a>' +
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
        '<div class="stat-row"><span class="stat-label">Profitable</span><span class="stat-value">' + analysis.profitable_count + ' / ' + known + ' (' + fmtPct(analysis.profitable_pct) + ')</span></div>' +
        '<div class="stat-row"><span class="stat-label">Unknown</span><span class="stat-value">' + analysis.unknown_count + '</span></div>' +
        '<div class="stat-row"><span class="stat-label">Avg PNL (cash)</span><span class="stat-value ' + pnlClass(analysis.avg_overall_pnl) + '">' + fmtUSD(analysis.avg_overall_pnl) + '</span></div>' +
        '<div class="stat-row"><span class="stat-label">Avg PNL (realized)</span><span class="stat-value ' + pnlClass(analysis.avg_realized_pnl) + '">' + fmtUSD(analysis.avg_realized_pnl) + '</span></div>' +
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
            '<thead><tr><th>Wallet</th><th>Amount</th><th>PNL</th><th>Status</th></tr></thead>' +
            '<tbody>';

    for (var i = 0; i < holders.length; i++) {
      var h = holders[i];
      var cls = pnlClass(h.overall_pnl);
      var status = h.is_on_leaderboard ? (h.overall_pnl > 0 ? "Profitable" : "Losing") : "Unknown";
      html +=
        '<tr class="' + cls + '">' +
          '<td class="wallet">' + (h.username || shortAddr(h.wallet_address)) + '</td>' +
          '<td>' + fmt(h.amount, 0) + '</td>' +
          '<td class="' + cls + '">' + fmtUSD(h.overall_pnl) + '</td>' +
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

  /* ── Collapsible sections (event delegation) ── */

  document.addEventListener("click", function (e) {
    var toggle = e.target.closest(".collapsible-toggle");
    if (!toggle) return;
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

  /* ── Prefill from shareable URL ── */

  if (window.__PREFILL_URL__) {
    urlInput.value = window.__PREFILL_URL__;
    startAnalysis(window.__PREFILL_URL__);
  }
})();
