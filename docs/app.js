/* CS Career Map: a static page that reads docs/data/*.json. No build step. */
(function () {
  "use strict";

  var REPO = "https://github.com/EmmaZhao422/cs-career-map";
  var SMALL_SAMPLE = 30;
  var BANDS = [
    { tier: "most", title: "In most postings" },
    { tier: "many", title: "In many postings" },
    { tier: "some", title: "In some postings" },
    { tier: "rare", title: "Rarely mentioned" }
  ];

  var main = document.getElementById("main");
  var cache = {};
  var state = { entryOnly: false, category: "All", open: null };

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

  function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s"); }

  function niceDate(iso) {
    if (!iso) return "";
    var d = new Date(iso.length === 10 ? iso + "T00:00:00Z" : iso);
    return d.toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", timeZone: "UTC" });
  }

  function pctText(p) { return (p >= 10 ? Math.round(p) : Math.round(p * 10) / 10) + "%"; }

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

  // ---------- home ----------
  function renderHome(index) {
    var total = index.roles.reduce(function (s, r) { return s + r.postings; }, 0);
    var list = h("ul", { class: "jobs" }, index.roles.map(function (role) {
      return h("li", {}, h("a", { class: "job", href: "#" + role.id }, [
        h("div", {}, [
          h("p", { class: "job-name", text: role.title }),
          h("p", { class: "job-blurb", text: role.blurb }),
          h("p", { class: "job-count", text: role.postings
            ? plural(role.postings, "posting") + " from " + (role.companies === 1 ? "1 company" : role.companies + " companies")
            : "No postings collected yet" })
        ]),
        h("ul", { class: "mini", "aria-label": "Most requested skills" }, role.top_skills.map(function (s) {
          return h("li", {}, [
            h("span", { class: "track" }, [
              h("i", { class: "stroke", style: "width:" + Math.min(100, s.pct) + "%", "aria-hidden": "true" }),
              h("span", { class: "name", text: s.name })
            ]),
            h("span", { class: "pct", text: pctText(s.pct) })
          ]);
        }))
      ]));
    }));

    show([
      h("h1", { text: "Which skills do job postings ask for? We counted." }),
      h("p", { class: "lede", text: "CS Career Map reads public job postings from company career pages, counts how often each skill comes up, and points you to one good place to learn it." }),
      h("p", { class: "note", text: total
        ? plural(total, "posting") + " read so far across " + plural(index.roles.length, "job") + ". Pick the job you want."
        : "No postings have been collected yet." }),
      list,
      h("h2", { text: "Hiring for one of these jobs?" }),
      h("p", { class: "note" }, [
        "Postings are wish lists. If you interview or hire for one of these roles, tell students what you look for in practice. ",
        h("a", { href: issueLink("practitioner-note.yml", "Practitioner note: "), text: "Add a practitioner note" }), "."
      ])
    ]);
  }

  // ---------- role ----------
  function renderRole(role, skills, notes, index) {
    var baseTotal = state.entryOnly ? role.entry_postings : role.postings;
    var rows = role.skills.map(function (s) {
      var count = state.entryOnly ? s.entry_count : s.count;
      var pct = baseTotal ? 100 * count / baseTotal : 0;
      return { s: s, count: count, pct: pct, tier: tierFor(pct, index.tiers) };
    }).filter(function (r) { return r.count > 0; });
    rows.sort(function (a, b) { return b.count - a.count || a.s.name.localeCompare(b.s.name); });

    var categories = ["All"].concat(rows.map(function (r) { return r.s.category; })
      .filter(function (c, i, all) { return all.indexOf(c) === i; }));
    if (categories.indexOf(state.category) < 0) state.category = "All";
    var visible = rows.filter(function (r) { return state.category === "All" || r.s.category === state.category; });

    function rerender() { renderRole(role, skills, notes, index); }

    var summary = "Based on " + plural(role.postings, "posting") + " from " +
      (role.companies === 1 ? "1 company" : role.companies + " companies") +
      (role.last_seen_to ? ", last read " + niceDate(role.last_seen_to) : "") + ". " +
      (role.entry_postings ? role.entry_postings + " of them are intern or new-grad postings." : "");

    var controls = h("div", { class: "controls" }, [
      h("div", { class: "seg", role: "group", "aria-label": "Which postings to count" }, [
        h("button", { type: "button", "aria-pressed": String(!state.entryOnly), text: "All postings",
          onclick: function () { state.entryOnly = false; rerender(); } }),
        h("button", { type: "button", "aria-pressed": String(state.entryOnly), text: "Intern and new grad only",
          onclick: function () { state.entryOnly = true; rerender(); } })
      ]),
      h("div", { class: "chips", role: "group", "aria-label": "Skill category" }, categories.map(function (c) {
        return h("button", { type: "button", "aria-pressed": String(state.category === c), text: c,
          onclick: function () { state.category = c; rerender(); } });
      }))
    ]);

    var sampleNote = null;
    if (!role.postings) {
      sampleNote = h("p", { class: "note", text: "No postings have been collected for this job yet." });
    } else if (baseTotal < SMALL_SAMPLE) {
      sampleNote = h("p", { class: "note", text: "Small sample: only " + plural(baseTotal, "posting") + " counted here, so treat the shares as rough." });
    }

    var bands = BANDS.map(function (band) {
      var inBand = visible.filter(function (r) { return r.tier === band.tier; });
      if (!inBand.length) return null;
      var range = band.tier === "most" ? index.tiers.most + "% or more"
        : band.tier === "many" ? index.tiers.many + "% to " + index.tiers.most + "%"
        : band.tier === "some" ? index.tiers.some + "% to " + index.tiers.many + "%"
        : "under " + index.tiers.some + "%";
      return h("section", { class: "band " + band.tier }, [
        h("h2", {}, [band.title, h("small", { text: range + " of postings" })]),
        h("ul", { class: "skills" }, inBand.map(function (r) {
          return skillRow(r, role, skills, notes, baseTotal, rerender);
        }))
      ]);
    });

    show([
      h("a", { class: "back", href: "#home", text: "All jobs" }),
      h("h1", { class: "role-title", text: role.title }),
      h("p", { class: "summary", text: summary }),
      controls,
      sampleNote,
      h("div", {}, bands),
      sourcesBlock(role)
    ], role.title);

    if (state.open) {
      var target = document.getElementById("skill-" + state.open);
      if (target && state.scrollToOpen) { target.scrollIntoView({ block: "center" }); target.focus(); }
      state.scrollToOpen = false;
    }
  }

  function skillRow(r, role, skills, notes, baseTotal, rerender) {
    var id = r.s.id;
    var isOpen = state.open === id;
    var button = h("button", {
      class: "skill-btn", type: "button", id: "skill-" + id, "aria-expanded": String(isOpen),
      "aria-controls": "detail-" + id,
      onclick: function () { state.open = isOpen ? null : id; rerender(); }
    }, [
      h("span", { class: "track" }, [
        h("i", { class: "stroke", style: "width:" + Math.max(1, Math.min(100, r.pct)) + "%", "aria-hidden": "true" }),
        h("span", { class: "name", text: r.s.name })
      ]),
      h("span", { class: "tally" }, [h("b", { text: String(r.count) }), " of " + baseTotal + " postings"])
    ]);
    return h("li", {}, [button, isOpen ? skillDetail(r, role, skills[id] || {}, skills, notes, rerender) : null]);
  }

  function skillDetail(r, role, meta, skills, notes, rerender) {
    var parts = [];
    if (meta.level) {
      parts.push(h("h3", { text: "What knowing it looks like" }), h("p", { text: meta.level }));
    }
    if (meta.prereqs && meta.prereqs.length) {
      var links = [];
      meta.prereqs.forEach(function (pid, i) {
        if (i) links.push(", ");
        links.push(h("button", { class: "prereq", type: "button", text: (skills[pid] || {}).name || pid,
          onclick: function () {
            state.open = pid; state.category = "All"; state.scrollToOpen = true; rerender();
          } }));
      });
      parts.push(h("h3", { text: "Learn first" }), h("p", {}, links));
    }
    if (meta.resources && meta.resources.length) {
      parts.push(h("h3", { text: "Learn it here" }), h("ul", {}, meta.resources.map(function (res) {
        return h("li", {}, [
          h("a", { href: res.url, text: res.title }),
          h("span", { class: "by", text: " by " + res.by + (res.free ? ", free" : "") + ". Link checked " + niceDate(res.checked) + "." })
        ]);
      })));
    }
    if (meta.project) {
      parts.push(h("h3", { text: "Prove it" }), h("p", { text: meta.project }));
    }
    if (!meta.level && !(meta.resources && meta.resources.length)) {
      parts.push(h("p", { text: "No learning guide for this skill yet." }));
    }

    var mine = notes.filter(function (n) { return n.skill === r.s.id && (!n.role || n.role === role.id); });
    if (mine.length) {
      parts.push(h("h3", { text: "From people who hire" }));
      mine.forEach(function (n) {
        parts.push(h("blockquote", {}, [h("p", { text: n.note }), h("footer", { text: n.who })]));
      });
    }

    parts.push(h("p", { class: "evidence", text:
      "Mentioned by " + (r.s.companies === 1 ? "1 company" : r.s.companies + " companies") +
      " in " + plural(r.s.count, "posting") + " overall. The guide above is written by people, not taken from postings." }));
    parts.push(h("p", { class: "ask" }, [
      h("a", { href: issueLink("suggest-resource.yml", "Resource for " + r.s.name + ": "), text: "Suggest a better resource" }),
      " or ",
      h("a", { href: issueLink("practitioner-note.yml", "Practitioner note on " + r.s.name + " (" + role.title + ")"), text: "add a note from the hiring side" }),
      "."
    ]));
    return h("div", { class: "detail", id: "detail-" + r.s.id }, parts);
  }

  function sourcesBlock(role) {
    if (!role.postings) return null;
    return h("section", {}, [
      h("h2", { text: "Where these numbers come from" }),
      h("p", { class: "note", text: "Every count on this page comes from the postings below. We keep a link and the list of skills each posting mentions, and nothing else." }),
      h("details", {}, [
        h("summary", { text: "Companies (" + role.companies + ")" }),
        h("ul", { class: "sources" }, role.company_counts.map(function (c) {
          return h("li", {}, [c[0] + " ", h("span", { class: "n", text: String(c[1]) })]);
        }))
      ]),
      h("details", {}, [
        h("summary", { text: "Postings (" + role.postings + ")" }),
        h("ul", { class: "postings" }, role.sample.map(function (p) {
          var title = p.url ? h("a", { href: p.url, text: p.title }) : h("span", { text: p.title });
          return h("li", {}, [title, h("span", { class: "where", text: " at " + p.company + (p.location ? ", " + p.location : "") })]);
        }))
      ])
    ]);
  }

  // ---------- how it works ----------
  function renderMethod(index) {
    show([
      h("a", { class: "back", href: "#home", text: "All jobs" }),
      h("h1", { class: "role-title", text: "How the numbers are made" }),
      h("ol", { class: "steps" }, [
        h("li", { text: "Once a week a script reads the public job boards of the companies on our list. These are the same listings you see on each company's careers page." }),
        h("li", { text: "It keeps postings whose title matches one of our jobs and skips senior, staff, lead and manager titles." }),
        h("li", { text: "For each posting it checks which skills from our list are mentioned, then saves the link and those skill names. The posting text is not stored." }),
        h("li", { text: "The site shows, for each skill, how many postings mention it. A posting stays in the sample for 120 days after it was last seen open." })
      ]),
      h("h2", { text: "What this cannot tell you" }),
      h("ul", { class: "plain" }, [
        h("li", { text: "Postings are wish lists. A skill that is listed is not always tested, and interviews test things postings never mention." }),
        h("li", { text: "We only read companies that publish through Greenhouse or Lever. Companies with their own careers system, including several of the largest, are not counted yet." }),
        h("li", { text: "Matching is by keyword. It can miss a skill described in unusual words and can over-count a word used in another sense." }),
        h("li", { text: "A company with many open postings weighs more. Each skill also shows how many different companies mention it." }),
        h("li", { text: "The learning guides and the 'learn first' links are written by people. They are opinions, and you can challenge them." })
      ]),
      h("h2", { text: "Help make it better" }),
      h("p", { class: "note" }, [
        "The company list, the skill list and the guides are plain files in the repository. ",
        h("a", { href: REPO, text: "Open the repository" }), " to add a company, fix a pattern, or suggest a resource."
      ]),
      index.demo ? h("p", { class: "note", text: "This copy of the site is showing demo data: the collection script has not run yet." }) : null
    ], "How it works");
  }

  // ---------- routing ----------
  function route() {
    var name = (location.hash || "#home").slice(1);
    getJSON("data/index.json").then(function (index) {
      document.getElementById("demo-banner").hidden = !index.demo;
      document.getElementById("updated").textContent = "Data last built " + niceDate(index.generated_at) + ".";
      if (name === "how-it-works") return renderMethod(index);
      var role = index.roles.filter(function (r) { return r.id === name; })[0];
      if (!role) return renderHome(index);
      state = { entryOnly: false, category: "All", open: null };
      return Promise.all([
        getJSON("data/roles/" + role.id + ".json"), getJSON("data/skills.json"), getJSON("data/notes.json")
      ]).then(function (got) { renderRole(got[0], got[1], got[2], index); });
    }).then(function () {
      window.scrollTo(0, 0);
    }).catch(function (err) {
      show([h("p", { class: "error", text: "The data could not be loaded. Reload the page to try again. (" + err.message + ")" })]);
    });
  }

  window.addEventListener("hashchange", route);
  route();
})();
