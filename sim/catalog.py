"""Detection rules and attack/insider behaviour templates. ALL DATA IS SYNTHETIC.

The two halves are written independently: TEMPLATES describe what an attacker or a departing insider does as a
sequence of telemetry events (they never mention a rule). RULES are detection logic over event attributes (they
never mention a template). Which rule catches which scenario is DERIVED by replaying rules against scenarios.

Modelling assumptions (stated, not hidden):
- Each telemetry action is consumed by the rules listed here and by no other rule. In particular no other rule reads
  endpoint DLP, USB or mail-gateway telemetry, and D021 reads proxy uploads only.
- Event `vol` is a normalised 0-100 magnitude (failed-login count, bytes, files touched). Attack steps are drawn from
  a higher-magnitude distribution than benign events, with per-action overlap set below.
"""

PERSONAL = ["personal_cloud", "personal_email", "usb"]
INSIDER_ACTIONS = ["net_upload", "cloud_sync_upload", "email_attach_external", "usb_write"]


def R(id, name, tech, mins, tuned, healthy, actions, n_benign=0, ben=(2, 5), t0=0, **cond):
    return dict(id=id, name=name, tech=tech, mins=mins, tuned=tuned, healthy=healthy, actions=actions,
                n_benign=n_benign, ben=ben, t0=t0, metric=cond.pop("metric", "vol"), cond=cond)


# n_benign = benign events of that action per 30-day window (D021/D031 benign events are built in core.make_events)
RULES = [
    R("D001", "Failed Login Burst", "T1110", 6, 410, True, ["auth_fail"], 1199, (2, 6)),
    R("D002", "PowerShell Any Execution", "T1059.001", 8, 520, True, ["ps_exec"], 1500, (3, 3)),
    R("D003", "DNS Query to Rare TLD", "T1071.004", 7, 300, True, ["dns_rare_tld"], 898, (2, 6)),
    R("D004", "New Scheduled Task Created", "T1053.005", 9, 380, True, ["sched_task"], 779, (2, 6)),
    R("D005", "Document Application Spawns Child Process", "T1204.002", 10, 450, True, ["doc_child_proc"], 650, (2, 6)),
    R("D006", "Outbound Traffic Non-Standard Port", "T1571", 5, 600, True, ["outbound_nonstd"], 1098, (2, 6)),
    R("D007", "LSASS Memory Access", "T1003.001", 25, 20, True, ["lsass_access"], 7),
    R("D008", "Credential Dumper Command Line", "T1003", 30, 15, True, ["cred_dump_cmd"], 1),
    R("D009", "Ransomware Mass File Rename", "T1486", 40, 30, True, ["mass_rename"], 1),
    R("D010", "Known C2 Framework Beacon Signature", "T1071.001", 30, 25, True, ["c2_beacon"], 3),
    R("D011", "Kerberoasting Ticket Request", "T1558.003", 20, 45, True, ["tgs_request"], 10),
    R("D012", "Shadow Copy Deletion", "T1490", 25, 60, True, ["vss_delete"], 1),
    R("D013", "Suspicious Service Install", "T1543.003", 15, 40, True, ["svc_install"], 22),
    R("D014", "Golden Ticket Anomaly", "T1558.001", 45, 50, True, ["tgt_anomaly"], 1),
    R("D016", "WMI Remote Execution", "T1047", 15, 200, True, ["wmi_exec"], 78),
    R("D017", "Registry Run Key Modified", "T1547.001", 10, 250, True, ["reg_runkey"], 136),
    R("D018", "Rare Parent-Child Process Pair", "T1055", 12, 180, True, ["rare_proc_pair"], 101),
    R("D019", "Cloud Console Login New Country", "T1078.004", 10, 90, True, ["cloud_login_newgeo"], 60),
    R("D020", "Browser Credential File Access", "T1555.003", 15, 300, True, ["browser_cred"], 40),
    # Proxy uploads to unapproved destinations, large only (t0 = 55 on the magnitude score)
    R("D021", "Large Outbound Upload", "T1048", 14, 220, True, ["net_upload"], 0, t0=55,
      dest_in=["ext_unknown", "personal_cloud"]),
    R("D022", "Remote Desktop From Workstation", "T1021.001", 8, 150, True, ["rdp_ws"], 110),
    R("D023", "Archive Created in Temp Dir", "T1560.001", 11, 330, True, ["archive_tmp"], 89),
    R("D024", "Linux Sudo Brute Force", "T1110.001", 9, 120, False, ["sudo_fail"], 46),
    R("D025", "Proxy Category Uncategorized", "T1102", 6, 480, True, ["proxy_uncat"], 288),
    R("D026", "Endpoint Agent Tamper", "T1562.001", 20, 70, False, ["agent_tamper"], 19),
    R("D027", "Email Forwarding Rule Created", "T1114.003", 12, 160, True, ["mail_fwd_rule"], 33),
    R("D028", "DLL Search Order Hijack", "T1574.001", 22, 280, True, ["dll_hijack"], 26),
    R("D029", "Host Event Log Cleared", "T1070.001", 15, 100, False, ["evtlog_clear"], 15),
    R("D030", "Container Exec in Prod", "T1609", 18, 60, True, ["container_exec"], 17),
    # Insider risk: departing user, sensitive data, egress to a personal channel. Metric = how much off-scope
    # sensitive access the user did recently ("ros"). Technique IDs verified against attack.mitre.org
    # (T1114 Email Collection was rejected: it covers an adversary collecting a victim's mailbox, not egress).
    R("D031", "Departing-User Sensitive Data Egress", "T1213.003;T1567.002;T1052.001;T1048", 20, 140, True,
      INSIDER_ACTIONS, 0, metric="ros", dest_in=PERSONAL, sens_min=2, departing=1),
]

# Attack-step magnitude distributions (a, b of a Beta, scaled to 0-100); default (6, 2.5)
ATTACK_VOL = {"ps_exec": (5, 3), "auth_fail": (4, 3), "proxy_uncat": (4, 3), "sched_task": (5, 3)}
CONFIRM_PROB = {"default": 0.9, "D031": 0.25}  # chance an analyst confirms a true-positive alert


def S(action, p=1.0, **kw):
    return dict(action=action, p=p, **kw)


# baseline = scenario instances in the 30-day baseline window (natural prevalence); replay = per-seed campaign size.
# Baseline counts were fixed once and not tuned afterwards; rules near the 5% precision cutoff move between
# verdicts with the window draw, which is itself an observation about rule-only triage.
TEMPLATES = [
    dict(name="credential_theft", baseline=12, steps=[S("auth_fail"), S("lsass_access", .9), S("cred_dump_cmd", .6)]),
    dict(name="phishing_execution", baseline=8, steps=[S("doc_child_proc"), S("ps_exec", .7), S("sched_task", .5),
                                                      S("c2_beacon", .6), S("dns_rare_tld", .5)]),
    dict(name="lateral_movement", baseline=8, steps=[S("rdp_ws"), S("wmi_exec", .6), S("svc_install", .5),
                                                    S("rare_proc_pair", .5)]),
    dict(name="ransomware", baseline=6, steps=[S("ps_exec", .5), S("vss_delete", .8), S("mass_rename"),
                                              S("evtlog_clear", .4)]),
    dict(name="kerberos_abuse", baseline=14, steps=[S("tgs_request"), S("tgt_anomaly", .35), S("lsass_access", .5)]),
    dict(name="persistence", baseline=6, steps=[S("reg_runkey", .8), S("sched_task", .6), S("dll_hijack", .4),
                                               S("agent_tamper", .5)]),
    dict(name="external_exfil", baseline=5, steps=[S("archive_tmp", .8), S("net_upload", dest="ext_unknown"),
                                                  S("outbound_nonstd", .5), S("dns_rare_tld", .4)]),
    dict(name="c2_over_proxy", baseline=5, steps=[S("proxy_uncat"), S("c2_beacon", .5), S("outbound_nonstd", .6)]),
    dict(name="cloud_account_takeover", baseline=5, steps=[S("cloud_login_newgeo"), S("mail_fwd_rule", .6),
                                                          S("browser_cred", .3)]),
    dict(name="container_breakout", baseline=3, steps=[S("container_exec"), S("sudo_fail", .5)]),
    dict(name="browser_cred_theft", baseline=4, steps=[S("browser_cred"), S("archive_tmp", .6),
                                                      S("net_upload", .7, dest="ext_unknown")]),
    # Insider scenarios (departing employee): bulk read outside normal project scope, then egress. Natural
    # prevalence in the baseline window is 0 (rare event); the replay campaign includes them.
    dict(name="insider_browser_bulk_upload", baseline=0, insider=True,
         steps=[S("repo_bulk_read"), S("net_upload", dest="personal_cloud", vol=(8, 2))]),
    dict(name="insider_low_and_slow_upload", baseline=0, insider=True,
         steps=[S("repo_bulk_read"), S("net_upload", dest="personal_cloud", vol=(2, 6), reps=4)]),
    dict(name="insider_sync_client", baseline=0, insider=True,
         steps=[S("repo_bulk_read"), S("cloud_sync_upload", dest="personal_cloud", vol=(7, 2))]),
    dict(name="insider_personal_email", baseline=0, insider=True,
         steps=[S("repo_bulk_read"), S("email_attach_external", dest="personal_email", vol=(6, 3))]),
    dict(name="insider_usb_copy", baseline=0, insider=True,
         steps=[S("repo_bulk_read"), S("usb_write", dest="usb", vol=(7, 2))]),
]
