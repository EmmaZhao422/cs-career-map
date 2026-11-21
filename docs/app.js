/* CS Career Map: a static page that reads docs/data/*.json. No build step. */
(function () {
  "use strict";

  var REPO = "https://github.com/EmmaZhao422/cs-career-map";
  var COACH = REPO + "/tree/main/skill/cs-career-coach";
  var SMALL_SAMPLE = 25;      // companies; below this the shares are rough
  var RARE_COMPANIES = 3;     // skills named by fewer companies are tucked away
  var START_MAX = 6;
  var PAGE_SIZE = 100;
  var PEOPLE = "Working with people";
  var BANDS = [
    { tier: "most", title: "Most ask for it" },
    { tier: "many", title: "Many ask for it" },
    { tier: "some", title: "Some ask for it" }
  ];

  var main = document.getElementById("main");
  var cache = {};
  // View options live in memory and survive opening rows and moving between jobs.
  var view = { byCompany: true, entryOnly: false };
  var page = null;          // what is on screen now
  var homeScroll = 0;
  var firstRoute = true;

  if ("scrollRestoration" in history) history.scrollRestoration = "manual";

  // ---------- small helpers ----------
  function h(tag, attrs, children) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v === true ? "" : v);
    });
    [].concat(children || []).forEach(function (c) {
      if (c === null || c === undefined || c === false) return;
      el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
    return el;
  }

  function getJSON(path) {
    if (!cache[path]) {
      cache[path] = fetch(path).then(function (r) {
        if (!r.ok) throw new Error(path + " returned " + r.status);
        return r.json();
      });
    }
    return cache[path];
  }

  function has(v) { return v !== null && v !== undefined; }
  function plural(n, word, many) { return n + " " + (n === 1 ? word : (many || word + "s")); }
  function companiesWord(n) { return n === 1 ? "company" : "companies"; }

  function niceDate(iso) {
    if (!iso) return "";
    var d = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso);
    return d.toLocaleDateString("en-GB", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
  }

  // Every percentage on the site goes through these two functions, from raw counts.
  function share(num, den) { return den ? 100 * num / den : 0; }
  function pctText(p) { return (p >= 10 || p === 0 ? Math.round(p) : Math.round(p * 10) / 10) + "%"; }

  function tierFor(pct, tiers) {
    if (pct >= tiers.most) return "most";
    if (pct >= tiers.many) return "many";
    if (pct >= tiers.some) return "some";
    return "rare";
  }

  function issueLink(template, title) {
    return REPO + "/issues/new?template=" + template + "&title=" + encodeURIComponent(title);
  }

  function show(nodes, title) {
    main.replaceChildren.apply(main, [].concat(nodes).filter(Boolean));
    document.title = title ? title + " | CS Career Map" : "CS Career Map";
  }

  function segmented(label, options, current, onPick) {
    return h("div", { class: "seg", role: "group", "aria-label": label }, options.map(function (o) {
      return h("button", { type: "button", "aria-pressed": String(o.value === current), text: o.label, "data-value": String(o.value),
        onclick: function (e) {
          [].forEach.call(e.currentTarget.parentNode.children, function (b) {
            b.setAttribute("aria-pressed", String(b === e.currentTarget));
          });
          onPick(o.value);
        } });
    }));
  }

  // ---------- home ----------
  function renderHome(index, roleFiles) {
    var byId = {};
    (roleFiles || []).forEach(function (r) { if (r) byId[r.id] = r; });
    var total = index.roles.reduce(function (s, r) { return s + r.postings; }, 0);
    var list = h("ul", { class: "jobs" }, index.roles.map(function (role) {
      var file = byId[role.id];
      var named = {};
      if (file) file.skills.forEach(function (s) { named[s.name] = s; });
      // Shares are computed from the role file's raw counts, exactly as on the job page.
      var tops = (role.top_skills || []).map(function (s) {
        var c = named[s.name];
        if (c && has(c.companies) && file.companies) return { name: s.name, p: share(c.companies, file.companies), co: true };
        if (c && file.postings) return { name: s.name, p: share(c.count, file.postings), co: false };
        return { name: s.name, p: has(s.company_pct) ? s.company_pct : s.pct, co: has(s.company_pct) };
      });
      var usesCompanies = tops.some(function (s) { return s.co; });
      var small = role.postings && role.companies < SMALL_SAMPLE;
      return h("li", {}, h("a", { class: "job", href: "#" + role.id }, [
        h("div", {}, [
          h("h2", { class: "job-name", text: role.title }),
          h("p", { class: "job-blurb", text: role.blurb }),
          h("p", { class: "job-count", text: role.postings
            ? plural(role.postings, "posting") + " from " + plural(role.companies, "company", "companies") +
              (small ? " (small sample)" : "")
            : "No postings collected yet" })
        ]),
        h("div", { class: "mini-wrap" }, [
          h("p", { class: "mini-label", text: usesCompanies ? "Share of companies asking" : "Share of postings asking" }),
          h("ul", { class: "mini", "aria-label": usesCompanies ? "Most requested skills, share of companies" : "Most requested skills, share of postings" },
            tops.map(function (s) {
              var p = s.p;
              return h("li", {}, [
                h("span", { class: "bar" }, [
                  h("i", { class: "stroke", style: "width:" + Math.max(1.5, Math.min(100, p)) + "%", "aria-hidden": "true" }),
                  h("span", { class: "name", text: s.name })
                ]),
                h("span", { class: "pct", text: pctText(p) })
              ]);
            }))
        ])
      ]));
    }));

    var fact1 = h("li", {}, [h("b", { text: "Real postings. " }),
      "Taken from the public job boards of the companies we follow, and recounted every Monday."]);
    var facts = h("ul", { class: "facts" }, [
      fact1,
      h("li", {}, [h("b", { text: "Each company counted once. " }),
        "A company with a hundred postings weighs the same as one with three, unless you switch to counting postings."]),
      h("li", {}, [h("b", { text: "Every learning link checked. " }),
        "Each guide links to at most two resources, and every link was opened before it went on the site."])
    ]);

    show([
      h("h1", { text: "Which skills do job postings ask for? We counted." }),
      h("p", { class: "lede", text: "CS Career Map reads public job postings from company career pages, counts how many companies ask for each skill, and links to checked places to learn it." }),
      h("p", { class: "note", text: total
        ? plural(total, "posting") + " read so far across " + plural(index.roles.length, "job") + ". Pick the job you want."
        : "No postings have been collected yet." }),
      list,
      h("section", { class: "about", "aria-labelledby": "about-h" }, [
        h("h2", { id: "about-h", text: "What this is" }),
        facts,
        h("p", { class: "about-links" }, [
          "The code and data are ", h("a", { href: REPO, text: "on GitHub" }), ". ",
          "Prefer a plan to a chart? The ",
          h("a", { href: COACH, text: "Claude coach skill" }),
          " uses the same counts to build a study plan for one of these jobs and teach it one skill at a time."
        ])
      ]),
      h("h2", { text: "Hiring for one of these jobs?" }),
      h("p", { class: "note" }, [
        "Postings are wish lists. Some skills already carry notes summarised from companies' own public hiring pages. If you interview or hire for one of these jobs, tell students what you look for in practice. ",
        h("a", { href: issueLink("practitioner-note.yml", "Practitioner note: "), text: "Add a practitioner note" }), "."
      ])
    ]);

    // The number of distinct companies is the union of the jobs' company lists.
    var names = {};
    Object.keys(byId).forEach(function (k) { (byId[k].company_counts || []).forEach(function (c) { names[c[0]] = 1; }); });
    var n = Object.keys(names).length;
    if (n > 1) {
      fact1.replaceChildren(h("b", { text: "Real postings. " }),
        "From the public job boards of the " + n + " companies that have a posting for one of these jobs, recounted every Monday.");
    }
  }

  // ---------- role: measurement ----------
  function measure(role, index, byCompany) {
    var entry = view.entryOnly;
    var entryCo = has(role.entry_companies) && role.skills.every(function (s) { return has(s.entry_companies); });
    var byCo = byCompany && (!entry || entryCo);
    var den = entry ? (byCo ? role.entry_companies : role.entry_postings) : (byCo ? role.companies : role.postings);
    var rows = role.skills.map(function (s) {
      var num = entry ? (byCo ? s.entry_companies : s.entry_count) : (byCo ? s.companies : s.count);
      var co = entry ? (entryCo ? s.entry_companies : null) : s.companies;
      var pct = share(num, den);
      return {
        s: s, num: num, pct: pct, companies: co, tier: tierFor(pct, index.tiers),
        people: s.category === PEOPLE,
        rare: pct < index.tiers.some || (has(co) && co < RARE_COMPANIES)
      };
    }).filter(function (r) { return r.num > 0; });
    rows.sort(function (a, b) { return b.pct - a.pct || a.s.name.localeCompare(b.s.name); });
    return { rows: rows, den: den || 0, byCo: byCo, fellBack: byCompany && !byCo, entry: entry, entryCo: entryCo };
  }

  function unitText(m, n) {
    if (m.byCo) return companiesWord(n);
    return (m.entry ? "intern and new-grad " : "") + (n === 1 ? "posting" : "postings");
  }

  // ---------- role page ----------
  function renderRole(role, skills, notes, index) {
    page = {
      kind: "role", id: role.id, role: role, skills: skills, notes: notes, index: index,
      open: {}, pushed: {}, lastOpen: null, category: "All", showRare: false, rows: {}
    };

    var top = topEmployer(role);
    var summary = "Based on " + plural(role.postings, "posting") + " from " + plural(role.companies, "company", "companies") + "." +
      (role.entry_postings ? " " + role.entry_postings + " " + (role.entry_postings === 1 ? "is an intern or new-grad posting." : "are intern or new-grad postings.") : "") +
      (top && top.share >= 20 ? " Largest single employer: " + top.name + ", " + pctText(top.share) + " of postings." : "");

    var categories = ["All"].concat(role.skills.map(function (s) { return s.category; })
      .filter(function (c, i, all) { return all.indexOf(c) === i; }));

    page.status = h("div", { class: "status" });
    page.live = h("p", { class: "sr-only", "aria-live": "polite" });
    page.list = h("div", { class: "list" });

    var controls = h("div", { class: "controls" }, [
      segmented("Count by", [
        { value: true, label: "By company" }, { value: false, label: "By posting" }
      ], view.byCompany, function (v) { view.byCompany = v; renderList(); }),
      segmented("Which postings to count", [
        { value: false, label: "All postings" }, { value: true, label: "Intern and new-grad only" }
      ], view.entryOnly, function (v) { view.entryOnly = v; renderList(); }),
      h("div", { class: "chip-row" }, [
        h("span", { class: "chip-label", id: "chips-label", text: "Category" }),
        h("div", { class: "chips", role: "group", "aria-labelledby": "chips-label" }, categories.map(function (c) {
          return h("button", { type: "button", "aria-pressed": String(c === "All"), text: c, "data-value": c,
            onclick: function (e) { setCategory(c, e.currentTarget.parentNode); } });
        }))
      ]),
      h("p", { class: "caveat", text: "Counts are keyword matches in the posting text. Listed is not the same as required." })
    ]);
    page.chips = controls.querySelector(".chips");

    show([
      h("a", { class: "back", href: "#home", text: "All jobs" }),
      h("h1", { class: "role-title", text: role.title }),
      h("p", { class: "summary", text: summary }),
      role.postings ? controls : h("p", { class: "note", text: "No postings have been collected for this job yet." }),
      page.status,
      page.live,
      page.list,
      sourcesBlock(role)
    ], role.title);

    if (role.postings) renderList();
  }

  function setCategory(c, chips) {
    page.category = c;
    [].forEach.call((chips || page.chips).children, function (b) {
      b.setAttribute("aria-pressed", String(b.getAttribute("data-value") === c));
    });
    renderList();
  }

  // Rebuild only the skill list. Controls, open rows and open <details> stay as they are.
  function renderList() {
    var role = page.role, index = page.index;
    var m = measure(role, index, view.byCompany);
    page.m = m;
    page.rows = {};
    m.rows.forEach(function (r) { page.rows[r.s.id] = r; });

    // status line: what is being counted, and whether the sample is small
    var status = [];
    status.push(m.byCo
      ? "Share of the " + m.den + " " + (m.entry ? "companies with an intern or new-grad posting" : "companies with a posting for " + role.title) + "; each company counts once."
      : "Share of the " + m.den + " " + unitText(m, m.den) + "; a company with many postings weighs more.");
    if (m.fellBack) status.push("Intern and new-grad postings can only be counted by posting for now.");
    var coBase = m.entry ? (m.entryCo ? role.entry_companies : role.entry_postings) : role.companies;
    if (coBase < SMALL_SAMPLE) {
      status.push("Small sample: only " + coBase + " " + (m.entry && !m.entryCo ? "postings" : companiesWord(coBase)) + " here, so treat the shares as rough.");
    }
    var warn = coBase < SMALL_SAMPLE ? status.pop() : null;
    page.status.replaceChildren.apply(page.status, [h("p", { text: status.join(" ") })].concat(warn ? [h("p", { class: "warn", text: warn })] : []));

    var cat = page.category;
    var visible = m.rows.filter(function (r) { return cat === "All" || r.s.category === cat; });
    var tech = visible.filter(function (r) { return !r.people; });
    var common = tech.filter(function (r) { return !r.rare; });
    var rare = tech.filter(function (r) { return r.rare; });
    var people = visible.filter(function (r) { return r.people; });

    var parts = [];
    if (cat === "All") parts.push(startHere(m));

    BANDS.forEach(function (band) {
      var inBand = common.filter(function (r) { return r.tier === band.tier; });
      if (!inBand.length) return;
      var t = index.tiers;
      var range = band.tier === "most" ? t.most + "% or more"
        : band.tier === "many" ? t.many + "% to " + t.most + "%"
        : t.some + "% to " + t.many + "%";
      parts.push(h("section", { class: "band " + band.tier }, [
        h("h2", {}, [band.title, h("small", { text: range + " of " + (m.byCo ? "companies" : "postings") })]),
        h("ul", { class: "skills" }, inBand.map(skillRow))
      ]));
    });

    if (rare.length) {
      var rareBand = h("section", { class: "band rare", id: "rare-band", hidden: !page.showRare }, [
        h("h2", {}, ["Rarely mentioned", h("small", { text: "named by fewer than " + RARE_COMPANIES + " companies, or by under " + index.tiers.some + "% of " + (m.byCo ? "companies" : "postings") })]),
        h("ul", { class: "skills" }, rare.map(skillRow))
      ]);
      var rareBtn = h("button", { type: "button", class: "more", "aria-expanded": String(page.showRare), "aria-controls": "rare-band",
        text: rareLabel(rare.length),
        onclick: function () {
          page.showRare = !page.showRare;
          rareBand.hidden = !page.showRare;
          rareBtn.setAttribute("aria-expanded", String(page.showRare));
          rareBtn.textContent = rareLabel(rare.length);
          page.announce();
        } });
      page.rareReveal = function () {
        if (!page.showRare) rareBtn.click();
      };
      parts.push(h("div", { class: "rare-toggle" }, rareBtn), rareBand);
    } else {
      page.rareReveal = function () {};
    }

    if (people.length) {
      parts.push(h("section", { class: "band people" }, [
        h("h2", { text: "Also asked for: working with people" }),
        h("p", { class: "note", text: "These are loose keyword matches on everyday words like communication and collaboration, so read them as a rough signal, not a measurement." }),
        h("ul", { class: "skills" }, people.map(skillRow))
      ]));
    }

    if (!visible.length) {
      parts.push(h("p", { class: "note", text: "No skill in this category is mentioned in the postings counted here." }));
    }
    page.list.replaceChildren.apply(page.list, parts.filter(Boolean));
    page.announce = function () {
      var n = common.length + people.length + (page.showRare ? rare.length : 0);
      page.live.textContent = "Showing " + plural(n, "skill") + ", " + (m.byCo ? "by company" : "by posting") +
        (m.entry ? ", intern and new-grad postings only" : "") + (cat !== "All" ? ", category " + cat : "") +
        (!page.showRare && rare.length ? ". " + rare.length + " rarely mentioned hidden." : ".");
    };
    page.announce();
  }

  function rareLabel(n) {
    return page.showRare ? "Hide rarely mentioned skills" : "Show " + plural(n, "rarely mentioned skill");
  }

  function fraction(r, m) {
    return r.num + " of " + m.den + " " + unitText(m, m.den);
  }

  function topEmployer(role) {
    if (role.company_counts && role.company_counts.length && role.postings) {
      return { name: role.company_counts[0][0], share: share(role.company_counts[0][1], role.postings) };
    }
    if (role.top_company && has(role.top_company_share)) return { name: role.top_company, share: role.top_company_share };
    return null;
  }

  // A link that opens a skill row adds a history entry, so Back closes the row again.
  // Remember where the reader was, to return there.
  function rememberPlace(e) {
    history.replaceState({ scroll: window.scrollY, from: e.currentTarget.id || null }, "", location.hash);
  }

  // "Start here": the editorial order from the role file; the counts beside it are measured.
  function startHere(m) {
    var role = page.role, skills = page.skills;
    var inRole = {};
    role.skills.forEach(function (s) { inRole[s.id] = s; });
    var ids;
    var editorial = Array.isArray(role.start_here);
    if (editorial) {
      ids = role.start_here.filter(function (id) { return inRole[id]; });
    } else {
      ids = computedStart();
    }
    if (!ids.length) return null;
    var byId = {};
    m.rows.forEach(function (r) { byId[r.s.id] = r; });

    return h("section", { class: "start", "aria-labelledby": "start-h" }, [
      h("h2", { id: "start-h", text: "Start here" }),
      h("p", { class: "note", text: editorial
        ? "The order we suggest learning this job's skills in, fundamentals first. The order is our advice; the counts beside each skill are measured."
        : "Ordered by how many companies ask for each skill. The order is our advice; the counts beside each skill are measured." }),
      h("ol", { class: "start-list" }, ids.map(function (id) {
        var r = byId[id];
        var name = (skills[id] || {}).name || inRole[id].name || id;
        var label = r
          ? h("a", { href: "#" + role.id + "/" + id, id: "start-" + id, class: "start-name", text: name, onclick: rememberPlace })
          : h("span", { class: "start-name plain", text: name });
        var why;
        if (!r) {
          why = m.entry ? "Not counted in intern and new-grad postings yet" : "Not counted for this job yet";
        } else {
          why = r.num + " of " + m.den + " " + unitText(m, m.den);
          if (!(m.entry && m.den < 20)) why += ", " + pctText(r.pct);
        }
        return h("li", {}, [label, h("span", { class: "why", text: why })]);
      }))
    ]);
  }

  // Fallback when a role file has no editorial list: the most-asked technical skills, by company.
  function computedStart() {
    var cm = measure(page.role, page.index, true);
    return cm.rows.filter(function (r) { return !r.people && !r.rare; }).slice(0, START_MAX).map(function (r) { return r.s.id; });
  }

  function skillRow(r) {
    var id = r.s.id, m = page.m;
    var isOpen = !!page.open[id];
    var li = h("li", { id: "row-" + id });
    var button = h("button", {
      class: "skill-btn", type: "button", id: "skill-" + id, "aria-expanded": String(isOpen),
      "aria-controls": isOpen ? "detail-" + id : null,
      onclick: function () { toggleRow(id, li, button); }
    }, [
      h("span", { class: "bar" }, [
        h("i", { class: "stroke", style: "width:" + Math.max(1.5, Math.min(100, r.pct)) + "%", "aria-hidden": "true" }),
        h("span", { class: "name", text: r.s.name })
      ]),
      h("span", { class: "tally" }, [
        h("span", { class: "frac" }, [h("b", { text: String(r.num) }), " of " + m.den + " " + unitText(m, m.den)]),
        h("span", { class: "sep", text: ", " }),
        h("span", { class: "pct", text: pctText(r.pct) })
      ])
    ]);
    li.appendChild(button);
    if (isOpen) li.appendChild(skillDetail(r));
    return li;
  }

  function toggleRow(id, li, button, forceOpen, keepHash) {
    var detail = li.querySelector(".detail");
    var open = forceOpen === true ? true : !page.open[id];
    if (open) {
      page.open[id] = true;
      if (!detail) li.appendChild(skillDetail(page.rows[id]));
      else detail.hidden = false;
      page.lastOpen = id;
    } else {
      delete page.open[id];
      if (detail) detail.remove();
      if (page.lastOpen === id) {
        var rest = Object.keys(page.open);
        page.lastOpen = rest.length ? rest[rest.length - 1] : null;
      }
    }
    button.setAttribute("aria-expanded", String(open));
    if (open) button.setAttribute("aria-controls", "detail-" + id);
    else button.removeAttribute("aria-controls");
    var hash = "#" + page.id + (page.lastOpen ? "/" + page.lastOpen : "");
    if (!keepHash && location.hash !== hash) history.replaceState(history.state, "", hash);
  }

  function closeSkill(id) {
    var li = document.getElementById("row-" + id), btn = document.getElementById("skill-" + id);
    if (li && btn && page.open[id]) toggleRow(id, li, btn, false, true);
  }

  // Open a skill's row (from a deep link or a "learn first" link) and bring it into view.
  function openSkill(id, focus, smooth) {
    if (!page.rows[id]) return false;
    if (page.category !== "All" && page.rows[id].s.category !== page.category) setCategory("All");
    if (page.rows[id].rare && !page.rows[id].people) page.rareReveal();
    var li = document.getElementById("row-" + id);
    var btn = document.getElementById("skill-" + id);
    if (!li || !btn) return false;
    toggleRow(id, li, btn, true);
    btn.scrollIntoView({ block: "start", behavior: smooth && !reducedMotion() ? "smooth" : "auto" });
    if (focus) btn.focus({ preventScroll: true });
    return true;
  }

  function reducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function skillDetail(r) {
    var role = page.role, skills = page.skills, m = page.m;
    var meta = skills[r.s.id] || {};
    var parts = [];
    if (meta.level) {
      parts.push(h("h3", { text: "What knowing it looks like" }), h("p", { text: meta.level }));
    }
    if (meta.prereqs && meta.prereqs.length) {
      var links = [];
      meta.prereqs.forEach(function (pid, i) {
        if (i) links.push(", ");
        var name = (skills[pid] || {}).name || pid;
        if (page.rows[pid]) {
          links.push(h("a", { href: "#" + role.id + "/" + pid, id: "pre-" + r.s.id + "-" + pid, text: name, onclick: rememberPlace }));
        } else {
          links.push(h("span", { text: name + " " }), h("span", { class: "by", text: "(not counted for this job)" }));
        }
      });
      parts.push(h("h3", { text: "Learn first" }), h("p", {}, links));
    }
    var res = meta.resources || [];
    parts.push(h("h3", { text: "Learn it here" }));
    if (res.length) {
      parts.push(h("ul", {}, res.map(function (x) {
        return h("li", {}, [
          h("a", { href: x.url, text: x.title }),
          h("span", { class: "by", text: " by " + x.by + (x.free ? ", free" : "") })
        ]);
      })));
      var dates = res.map(function (x) { return x.checked; }).filter(Boolean).sort();
      if (dates.length) parts.push(h("p", { class: "by", text: "Links checked " + niceDate(dates[0]) + "." }));
    } else {
      parts.push(h("p", {}, ["We have not found a resource we can vouch for yet. ",
        h("a", { href: issueLink("suggest-resource.yml", "Resource for " + r.s.name + ": "), text: "Suggest one" }), "."]));
    }
    if (meta.project) {
      parts.push(h("h3", { text: "Prove it" }), h("p", { text: meta.project }));
    }

    var mine = page.notes.filter(function (n) { return n.skill === r.s.id && (!n.role || n.role === role.id); });
    if (mine.length) {
      var allPublished = mine.every(function (n) { return n.kind === "published"; });
      parts.push(h("h3", { text: allPublished ? "From company hiring pages" : "From the hiring side" }));
      mine.forEach(function (n) {
        var label = n.kind === "published" ? "Summarised from " : "Sent in by ";
        var who = n.source ? h("a", { href: n.source, text: n.who }) : n.who;
        parts.push(h("blockquote", {}, [h("p", { text: n.note }), h("footer", {}, [label, who, "."])]));
      });
    }

    var ev;
    if (m.entry) {
      ev = "Named in " + r.s.entry_count + " of " + role.entry_postings + " intern and new-grad postings" +
        (m.entryCo ? ", from " + r.s.entry_companies + " of " + role.entry_companies + " companies" : "") + ".";
    } else {
      ev = "Named by " + r.s.companies + " of " + role.companies + " companies, in " + r.s.count + " of " + role.postings + " postings.";
    }
    parts.push(h("p", { class: "evidence", text: ev + " The guide above is editorial advice, not something taken from postings." }));
    parts.push(h("p", { class: "ask" }, [
      h("a", { href: issueLink("suggest-resource.yml", "Resource for " + r.s.name + ": "), text: "Suggest a better resource" }),
      " or ",
      h("a", { href: issueLink("practitioner-note.yml", "Practitioner note on " + r.s.name + " (" + role.title + ")"), text: "add a note from the hiring side" }),
      "."
    ]));
    return h("div", { class: "detail", id: "detail-" + r.s.id }, parts);
  }

  function sourcesNote(role) {
    var top = topEmployer(role);
    return "Every count on this page comes from the postings below. We keep a link and the list of skills each posting mentions, and nothing else." +
      (role.last_seen_to ? " Postings last read " + niceDate(role.last_seen_to) + "." : "") +
      (role.listings > role.postings ? " The same title at one company is counted once, so " + role.listings + " listings became " + role.postings + " postings." : "") +
      " A posting stays in the sample for up to 120 days after it was last seen open." +
      (top && top.share >= 10 && top.share < 20 ? " The largest single employer, " + top.name + ", has " + pctText(top.share) + " of the postings; counting by company keeps it from outweighing the rest." : "");
  }

  function sourcesBlock(role) {
    if (!role.postings) return null;
    var postingsList = h("ul", { class: "postings" });
    var shown = 0;
    var more = h("button", { type: "button", class: "more", onclick: function () {
      var first = addPostings();
      if (shown >= role.sample.length && first) first.focus();
    } });
    function addPostings() {
      var batch = role.sample.slice(shown, shown + PAGE_SIZE);
      var firstLink = null;
      batch.forEach(function (p) {
        var title = p.url ? h("a", { href: p.url, text: p.title }) : h("span", { text: p.title });
        if (!firstLink && p.url) firstLink = title;
        postingsList.appendChild(h("li", {}, [title, h("span", { class: "where", text: " at " + p.company + (p.location ? ", " + p.location : "") })]));
      });
      shown += batch.length;
      var left = role.sample.length - shown;
      more.hidden = left <= 0;
      more.textContent = "Show more (" + left + " left)";
      return firstLink;
    }
    var postingsDetails = h("details", {}, [
      h("summary", { text: "Postings (" + role.sample.length + ")" }), postingsList, more
    ]);
    postingsDetails.addEventListener("toggle", function () {
      if (postingsDetails.open && !shown) addPostings();
    });
    more.hidden = true;

    return h("section", { class: "sources-block" }, [
      h("h2", { text: "Where these numbers come from" }),
      h("p", { class: "note", text: sourcesNote(role) }),
      h("details", {}, [
        h("summary", { text: "Companies (" + role.companies + ")" }),
        h("p", { class: "note", text: "Number of postings from each company." }),
        h("ul", { class: "sources" }, role.company_counts.map(function (c) {
          return h("li", {}, [c[0] + " ", h("span", { class: "n", text: String(c[1]) })]);
        }))
      ]),
      postingsDetails
    ]);
  }

  // ---------- how it works ----------
  function renderMethod(index) {
    show([
      h("a", { class: "back", href: "#home", text: "All jobs" }),
      h("h1", { class: "role-title", text: "How the numbers are made" }),
      h("ol", { class: "steps" }, [
        h("li", { text: "Once a week a script reads the public job boards of the companies on our list, through the Greenhouse and Lever job board APIs. These are the same postings you see on each company's careers page." }),
        h("li", { text: "It keeps postings whose title matches one of our jobs and skips senior, staff, lead and manager titles. The same title at one company counts once, even when it is listed in several locations." }),
        h("li", { text: "It looks for each skill in the body of the posting, then saves the link and the matched skill names. The posting text is not stored." }),
        h("li", { text: "Text a company repeats across its postings is ignored: any line shared by half or more of a company's distinct job titles, such as its introduction or benefits. So is the company's own name." }),
        h("li", { text: "By default each skill shows how many different companies ask for it, out of all the companies with a posting for that job. Each company counts once, so one employer with a hundred postings cannot outweigh the rest. You can switch to counting postings instead." }),
        h("li", { text: "A posting stays in the sample for up to 120 days after it was last seen open." })
      ]),
      h("p", { class: "note" }, [
        "The matching rules were checked against samples of real postings. What was found, fixed and left open is in ",
        h("a", { href: REPO + "/blob/main/AUDIT.md", text: "the matching audit (AUDIT.md)" }), "."
      ]),
      h("h2", { text: "What this cannot tell you" }),
      h("ul", { class: "plain" }, [
        h("li", { text: "Postings are wish lists. A skill that is listed is not always tested, and interviews test things postings never mention." }),
        h("li", { text: "We only read companies that publish through Greenhouse or Lever. Companies with their own careers system, including several of the largest, are not counted yet." }),
        h("li", { text: "The sample leans toward venture-backed tech companies, so it may say less about other kinds of employers." }),
        h("li", { text: "A few large employers post far more than others. That is why the default view counts companies, not postings." }),
        h("li", { text: "Matching is by keyword. It can miss a skill described in unusual words and can over-count a word used in another sense. Skills about working with people are the loosest matches." }),
        h("li", { text: "\"Start here\" is editorial: it is the order we would learn things in for each job, fundamentals first, not a ranking by count. The counts shown beside it are measured." }),
        h("li", { text: "The learning guides and the \"learn first\" links are editorial opinions too, first drafted with an AI model. Every linked resource was opened and checked. You can challenge any of them." })
      ]),
      h("h2", { text: "Help make it better" }),
      h("p", { class: "note" }, [
        "The company list, the skill list and the guides are plain files in the repository. ",
        h("a", { href: REPO, text: "Open the repository" }), " to add a company, fix a pattern, or suggest a resource."
      ]),
      index.demo ? h("p", { class: "note", text: "This copy of the site is showing demo data: the collection script has not run yet." }) : null
    ], "How it works");
  }

  function renderMissing(index) {
    show([
      h("h1", { class: "role-title", text: "No such page" }),
      h("p", { class: "lede", text: "That link does not match a page on this site. Pick a job instead:" }),
      h("ul", { class: "plain" }, index.roles.map(function (r) {
        return h("li", {}, h("a", { href: "#" + r.id, text: r.title }));
      })),
      h("p", { class: "note" }, [h("a", { href: "#home", text: "Go to the home page" }), "."])
    ], "No such page");
  }

  // ---------- routing ----------
  function parseHash() {
    var raw = (location.hash || "").replace(/^#/, "");
    try { raw = decodeURIComponent(raw); } catch (e) { /* keep raw */ }
    if (!raw || raw === "home") return { page: "home" };
    if (raw === "how-it-works") return { page: "how-it-works" };
    var bits = raw.split("/");
    return { page: "role", id: bits[0], skill: bits[1] || null, extra: bits.length > 2 };
  }

  function route() {
    var r = parseHash();
    if (page && page.kind === "home") homeScroll = window.scrollY;

    // Same job already on screen: open the linked skill in place, without rebuilding.
    if (r.page === "role" && page && page.kind === "role" && page.id === r.id && !r.extra) {
      // Rows opened by following a link close again when the reader goes Back.
      Object.keys(page.pushed).forEach(function (id) {
        if (id !== r.skill) { closeSkill(id); delete page.pushed[id]; }
      });
      var st = history.state || {};
      if (r.skill && !page.open[r.skill]) {
        page.pushed[r.skill] = 1;
        openSkill(r.skill, true, true);
      } else if (r.skill && !has(st.scroll)) {
        openSkill(r.skill, true, true);
      } else if (has(st.scroll)) {
        window.scrollTo(0, st.scroll);
        var from = st.from && document.getElementById(st.from);
        if (from) from.focus({ preventScroll: true });
      }
      return Promise.resolve();
    }

    return getJSON("data/index.json").then(function (index) {
      var banner = document.getElementById("demo-banner");
      var bannerText = index.demo
        ? "Demo data. These numbers are placeholders and the companies are invented. Real postings replace them after the first collection run."
        : (index.notice || "");
      banner.textContent = bannerText;
      banner.hidden = !bannerText;
      document.getElementById("updated").textContent = "Data last built " + niceDate(index.generated_at) + ".";

      if (r.page === "home") {
        return Promise.all(index.roles.map(function (x) {
          return getJSON("data/roles/" + x.id + ".json").catch(function () { return null; });
        })).then(function (files) {
          renderHome(index, files);
          page = { kind: "home" };
          return { scroll: homeScroll };
        });
      }
      if (r.page === "how-it-works") {
        renderMethod(index);
        page = { kind: "method" };
        return { scroll: 0 };
      }
      var role = index.roles.filter(function (x) { return x.id === r.id; })[0];
      if (!role || r.extra) {
        renderMissing(index);
        page = { kind: "missing" };
        return { scroll: 0 };
      }
      return Promise.all([
        getJSON("data/roles/" + role.id + ".json"), getJSON("data/skills.json"), getJSON("data/notes.json")
      ]).then(function (got) {
        renderRole(got[0], got[1], got[2], index);
        return { scroll: 0, skill: r.skill };
      });
    }).then(function (after) {
      var opened = false;
      window.scrollTo(0, after.scroll || 0);
      if (after.skill) {
        opened = openSkill(after.skill, true);
        if (!opened) history.replaceState(history.state, "", "#" + page.id);
      }
      if (!opened && !firstRoute) main.focus({ preventScroll: true });
      firstRoute = false;
    }).catch(function (err) {
      page = { kind: "error" };
      show([h("p", { class: "error", text: "The data could not be loaded. Reload the page to try again. (" + err.message + ")" })]);
    });
  }

  // "Skip to content" moves focus to the page body without changing the route.
  var skip = document.querySelector(".skip");
  if (skip) skip.addEventListener("click", function (e) {
    e.preventDefault();
    main.focus();
  });

  window.addEventListener("hashchange", route);
  route();
})();
