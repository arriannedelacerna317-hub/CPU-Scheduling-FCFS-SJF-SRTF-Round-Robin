import tkinter as tk
from collections import deque
from copy import deepcopy
from tkinter import ttk

IDLE = "IDLE"


class Process:
    def __init__(self, pid, at, bt, order):
        self.pid, self.at, self.bt, self.order = pid, at, bt, order
        self.remaining = bt
        self.start = None
        self.ct = 0

    @property
    def tat(self):
        return self.ct - self.at

    @property
    def wt(self):
        return self.tat - self.bt

    @property
    def rt(self):
        return self.start - self.at


def merge_segments(segments):
    merged = []
    for pid, s, e in segments:
        if merged and merged[-1][0] == pid and merged[-1][2] == s:
            merged[-1] = (pid, merged[-1][1], e)
        else:
            merged.append((pid, s, e))
    return merged


class Result:
    def __init__(self, key, name, procs, timeline, rr_log=None, quantum=None):
        self.key, self.name = key, name
        self.procs = sorted(procs, key=lambda p: p.order)
        self.gantt = timeline if rr_log is not None else merge_segments(timeline)
        self.end_time = timeline[-1][2]
        self.rr_log, self.quantum = rr_log, quantum

    def avg(self, attr):
        return sum(getattr(p, attr) for p in self.procs) / len(self.procs)


def fcfs(procs):
    procs, timeline, time = deepcopy(procs), [], 0
    for p in sorted(procs, key=lambda x: (x.at, x.order)):
        if time < p.at:
            timeline.append((IDLE, time, p.at))
            time = p.at
        p.start = time
        timeline.append((p.pid, time, time + p.bt))
        time += p.bt
        p.ct = time
    return Result("FCFS", "First Come First Served", procs, timeline)


def sjf(procs):
    procs, timeline, time, finished = deepcopy(procs), [], 0, set()
    while len(finished) < len(procs):
        ready = [p for p in procs if p.at <= time and p.pid not in finished]
        if not ready:
            nxt = min(p.at for p in procs if p.pid not in finished)
            timeline.append((IDLE, time, nxt))
            time = nxt
            continue
        p = min(ready, key=lambda x: (x.bt, x.at, x.order))
        p.start = time
        timeline.append((p.pid, time, time + p.bt))
        time += p.bt
        p.ct = time
        finished.add(p.pid)
    return Result("SJF", "Shortest Job First (non-preemptive)", procs, timeline)


def srtf(procs):
    procs, timeline, time, done = deepcopy(procs), [], 0, 0
    current = None
    while done < len(procs):
        ready = [p for p in procs if p.at <= time and p.remaining > 0]
        if not ready:
            nxt = min(p.at for p in procs if p.remaining > 0)
            timeline.append((IDLE, time, nxt))
            time, current = nxt, None
            continue
        best = min(ready, key=lambda x: (x.remaining, x.at, x.order))
        if current in ready and current.remaining == best.remaining:
            best = current
        current = best
        if current.start is None:
            current.start = time
        timeline.append((current.pid, time, time + 1))
        current.remaining -= 1
        time += 1
        if current.remaining == 0:
            current.ct = time
            done += 1
    return Result("SRTF", "Shortest Remaining Time First (preemptive)", procs, timeline)


def round_robin(procs, quantum):
    procs = deepcopy(procs)
    ordered = sorted(procs, key=lambda x: (x.at, x.order))
    queue, timeline, log = deque(), [], []
    time, i, done, n = 0, 0, 0, len(procs)

    def admit(t):
        nonlocal i
        while i < n and ordered[i].at <= t:
            queue.append(ordered[i])
            i += 1

    admit(0)
    while done < n:
        if not queue:
            nxt = ordered[i].at
            timeline.append((IDLE, time, nxt))
            time = nxt
            admit(time)
            continue
        p = queue.popleft()
        if p.start is None:
            p.start = time
        run, before, t0 = min(quantum, p.remaining), p.remaining, time
        time += run
        p.remaining -= run
        timeline.append((p.pid, t0, time))
        admit(time)
        if p.remaining > 0:
            queue.append(p)
            status = "Requeued"
        else:
            p.ct, status = time, "Finished"
            done += 1
        log.append({"pid": p.pid, "start": t0, "end": time, "before": before,
                    "after": p.remaining, "status": status,
                    "queue": [q.pid for q in queue]})
    return Result("RR", f"Round Robin (time quantum = {quantum})", procs,
                  timeline, rr_log=log, quantum=quantum)


BG, WHITE, BORDER = "#eef2f7", "#ffffff", "#cfd8e6"
NAVY, BLUE, GREEN = "#1f3a68", "#2f6fed", "#2e9e5b"
TEXT, MUTED, HEAD = "#1d2733", "#6b7788", "#e6edf8"
PASTEL = ["#a9c9f5", "#a8e6b4", "#f7c58f", "#f4a8c0", "#d0b8f0",
          "#f7e08f", "#9fe0e0", "#f2b0a8", "#c4d89a", "#b8c4e8"]

F = ("Segoe UI", 10)
F_B = ("Segoe UI", 10, "bold")
F_S = ("Segoe UI", 9)

DESCRIPTIONS = {
    "FCFS": "Processes run in the order they arrive. Once started, a process runs "
            "until it finishes (no preemption).",
    "SJF": "When the CPU is free, the ready process with the smallest burst time "
           "runs next, until it finishes (no preemption).",
    "SRTF": "Like SJF, but preemptive: the process with the least remaining time "
            "always gets the CPU, so a shorter newcomer can interrupt.",
}


def mkbtn(parent, text, cmd, bg="#e3e9f4", fg=TEXT, hover="#d2dbec", font=F_B, padx=12, pady=6):
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, font=font,
                  activebackground=hover, activeforeground=fg, relief="flat",
                  bd=0, padx=padx, pady=pady, cursor="hand2")
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


def make_table(parent, columns, headings, widths, height, anchors=None):
    tree = ttk.Treeview(parent, columns=columns, show="headings", height=height)
    for c, h, w in zip(columns, headings, widths):
        tree.heading(c, text=h)
        tree.column(c, width=w, anchor=(anchors or {}).get(c, "center"))
    return tree


def results_card(parent, title="Results"):
    outer = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
    tk.Label(outer, text=title, bg=NAVY, fg="white", font=("Segoe UI", 11, "bold"),
             anchor="w", padx=12, pady=5).pack(fill="x")
    body = tk.Frame(outer, bg=WHITE)
    body.pack(fill="both", expand=True, padx=12, pady=10)
    return outer, body


def done_badge(parent):
    tk.Label(parent, text="✔  Simulation Completed!", bg="#dff3e7", fg=GREEN,
             font=F_B, padx=12, pady=4).pack(side="right")


class AlgoView(tk.Frame):
    def __init__(self, master, colors, res):
        super().__init__(master, bg=BG)
        self.res, self.colors = res, colors

        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text=res.key, bg=BG, fg=NAVY, font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Label(head, text="   " + res.name, bg=BG, fg=MUTED, font=("Segoe UI", 11)).pack(side="left", pady=(7, 0))
        done_badge(head)

        card, body = results_card(self)
        card.pack(fill="both", expand=True)

        tk.Label(body, text="Gantt Chart:", bg=WHITE, fg=TEXT, font=F_B).pack(anchor="w")
        self.cv = tk.Canvas(body, height=84, bg=WHITE, highlightthickness=0)
        self.cv.pack(fill="x", pady=(4, 6))
        self.cv.bind("<Configure>", lambda e: self.draw_gantt())

        avg = tk.Frame(body, bg=HEAD)
        avg.pack(fill="x", pady=(0, 10))
        for label, attr in (("Average Completion Time", "ct"), ("Average Turnaround Time", "tat"),
                            ("Average Waiting Time", "wt"), ("Average Response Time", "rt")):
            f = tk.Frame(avg, bg=HEAD)
            f.pack(side="left", expand=True, pady=6)
            tk.Label(f, text=f"{res.avg(attr):.2f}", bg=HEAD, fg=NAVY, font=("Segoe UI", 15, "bold")).pack()
            tk.Label(f, text=label, bg=HEAD, fg=MUTED, font=F_S).pack()

        row = tk.Frame(body, bg=WHITE)
        row.pack(fill="both", expand=True)
        row.columnconfigure(1, weight=1)
        row.rowconfigure(0, weight=1)

        left = tk.Frame(row, bg=WHITE)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        tk.Label(left, text="Details:", bg=WHITE, fg=TEXT, font=F_B).pack(anchor="w", pady=(0, 4))
        tree = make_table(left, ("pid", "at", "bt", "ct", "tat", "wt", "rt"),
                          ("Process", "Arrival", "Burst", "CT", "TAT", "WT", "RT"),
                          (66, 60, 50, 50, 50, 50, 50), min(len(res.procs) + 1, 10))
        tree.tag_configure("avg", background=HEAD, foreground=NAVY, font=F_B)
        for p in res.procs:
            tree.insert("", "end", values=(p.pid, p.at, p.bt, p.ct, p.tat, p.wt, p.rt))
        tree.insert("", "end", tags=("avg",), values=(
            "AVG", "", "", f"{res.avg('ct'):.2f}", f"{res.avg('tat'):.2f}",
            f"{res.avg('wt'):.2f}", f"{res.avg('rt'):.2f}"))
        tree.pack(anchor="w")

        right = tk.Frame(row, bg=WHITE)
        right.grid(row=0, column=1, sticky="nsew")
        if res.rr_log:
            tk.Label(right, text=f"Round Robin Quantum Trace (q = {res.quantum}):", bg=WHITE,
                     fg=TEXT, font=F_B).pack(anchor="w", pady=(0, 4))
            tr = make_table(right, ("n", "time", "pid", "rem", "status", "queue"),
                            ("#", "Time", "Process", "Remaining", "Status", "Queue"),
                            (28, 66, 58, 84, 96, 110), 9, {"queue": "w"})
            for n, e in enumerate(res.rr_log, 1):
                q = ", ".join(e["queue"]) or "empty"
                tr.insert("", "end", values=(n, f"{e['start']} - {e['end']}", e["pid"],
                                             f"{e['before']} → {e['after']}", e["status"], q))
            sb = ttk.Scrollbar(right, orient="vertical", command=tr.yview)
            tr.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            tr.pack(side="left", fill="both", expand=True)
        else:
            tk.Label(right, text="How it works:", bg=WHITE, fg=TEXT, font=F_B).pack(anchor="w", pady=(0, 4))
            tk.Label(right, text=DESCRIPTIONS[res.key], bg=WHITE, fg=MUTED, font=("Segoe UI", 11),
                     wraplength=380, justify="left").pack(anchor="w")
            tk.Label(right, text="TAT = CT − AT\nWT = TAT − BT\nRT = first CPU time − AT", bg=WHITE,
                     fg=NAVY, font=("Consolas", 10), justify="left").pack(anchor="w", pady=(14, 0))

    def draw_gantt(self):
        cv, res = self.cv, self.res
        cv.delete("all")
        W = max(cv.winfo_width(), 400)
        x0, y, h = 12, 6, 46
        unit = (W - 2 * x0) / res.end_time
        last = -999
        for pid, s, e in res.gantt:
            xa, xb = x0 + s * unit, x0 + e * unit
            if pid == IDLE:
                cv.create_rectangle(xa, y, xb, y + h, fill="#e4e7ec", outline="#8a94a6", dash=(3, 3))
                if xb - xa > 34:
                    cv.create_text((xa + xb) / 2, y + h / 2, text="idle", fill=MUTED, font=F_S)
            else:
                cv.create_rectangle(xa, y, xb, y + h, fill=self.colors[pid], outline="#4a5a73")
                if xb - xa > 20:
                    cv.create_text((xa + xb) / 2, y + h / 2, text=pid, fill=TEXT, font=F_B)
            if xa - last >= 22:
                cv.create_text(xa, y + h + 12, text=str(s), fill=TEXT, font=F_S)
                last = xa
        xe = x0 + res.end_time * unit
        if xe - last >= 14:
            cv.create_text(xe, y + h + 12, text=str(res.end_time), fill=TEXT, font=F_S)


class CompareView(tk.Frame):
    COLS = (("Avg CT", "ct"), ("Avg TAT", "tat"), ("Avg WT", "wt"), ("Avg RT", "rt"))

    def __init__(self, master, results):
        super().__init__(master, bg=BG)
        self.results = results
        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", pady=(0, 6))
        tk.Label(head, text="Comparison", bg=BG, fg=NAVY, font=("Segoe UI", 20, "bold")).pack(side="left")
        done_badge(head)

        card, body = results_card(self)
        card.pack(fill="both", expand=True)

        tk.Label(body, text="Average metrics (lower is better, green = best):", bg=WHITE,
                 fg=TEXT, font=F_B).pack(anchor="w", pady=(0, 6))
        grid = tk.Frame(body, bg=BORDER)
        grid.pack(anchor="w")
        for c, h in enumerate(["Algorithm"] + [c[0] for c in self.COLS]):
            tk.Label(grid, text=h, bg=HEAD, fg=NAVY, font=F_B, width=16, pady=6).grid(
                row=0, column=c, padx=1, pady=1, sticky="nsew")
        best = {a: min(r.avg(a) for r in results) for _, a in self.COLS}
        for i, r in enumerate(results, 1):
            name = f"RR (q={r.quantum})" if r.key == "RR" else r.key
            tk.Label(grid, text=name, bg=WHITE, fg=TEXT, font=F_B, width=16, pady=6).grid(
                row=i, column=0, padx=1, pady=1, sticky="nsew")
            for c, (_, a) in enumerate(self.COLS, 1):
                v = r.avg(a)
                is_best = abs(v - best[a]) < 1e-9
                tk.Label(grid, text=f"{v:.2f}", bg="#dff3e7" if is_best else WHITE,
                         fg=GREEN if is_best else TEXT, font=F_B if is_best else F,
                         width=16, pady=6).grid(row=i, column=c, padx=1, pady=1, sticky="nsew")

        tk.Label(body, text="Short comparison:", bg=WHITE, fg=TEXT, font=F_B).pack(anchor="w", pady=(16, 4))
        for line in self.summary():
            tk.Label(body, text="•  " + line, bg=WHITE, fg=TEXT, font=F,
                     wraplength=820, justify="left").pack(anchor="w", pady=1)

    def summary(self):
        lines = []
        for label, attr in (("waiting time", "wt"), ("turnaround time", "tat"),
                            ("response time", "rt")):
            lo = min(r.avg(attr) for r in self.results)
            names = [r.key for r in self.results if abs(r.avg(attr) - lo) < 1e-9]
            lines.append(f"Lowest average {label}: {', '.join(names)} ({lo:.2f}).")
        lines += [
            "FCFS is the simplest, but a long job at the front delays every job behind it.",
            "SJF and SRTF usually give the lowest waiting time, but long jobs may starve.",
            "Round Robin is the fairest and responds quickly, but its waiting and "
            "turnaround times depend on the quantum size.",
        ]
        return lines


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CPU Scheduling Simulator")
        self.geometry("1360x800")
        self.minsize(1100, 700)
        self.configure(bg=BG)
        self.rows, self.view_frames = [], []
        self._style()
        tk.Label(self, text="CPU Scheduling Simulator", bg=BG, fg=NAVY,
                 font=("Segoe UI", 20, "bold")).pack(anchor="w", padx=16, pady=(10, 8))
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._sidebar(body)
        self.nb = ttk.Notebook(body)
        self.nb.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self._welcome()
        self._refresh_inputs()

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Treeview", background=WHITE, fieldbackground=WHITE, foreground=TEXT,
                    rowheight=26, bordercolor=BORDER, font=F)
        s.configure("Treeview.Heading", background=HEAD, foreground=NAVY, relief="flat", font=F_B)
        s.map("Treeview", background=[("selected", "#cfe0fb")], foreground=[("selected", TEXT)])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background="#dbe3f1", foreground=MUTED, padding=(22, 8),
                    font=F_B, borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", NAVY)], foreground=[("selected", "white")])

    def _welcome(self):
        f = tk.Frame(self.nb, bg=WHITE)
        tk.Label(f, text="Ready to simulate", bg=WHITE, fg=NAVY, font=("Segoe UI", 24, "bold")).pack(pady=(170, 6))
        tk.Label(f, text="Add your processes on the left, set the Round Robin quantum,\n"
                         "then click  ▶ Run Simulation.", bg=WHITE, fg=MUTED,
                 font=("Segoe UI", 12), justify="center").pack()
        self.nb.add(f, text="  Start  ")
        self.view_frames.append(f)

    def _entry(self, parent, width):
        return tk.Entry(parent, width=width, bg=WHITE, fg=TEXT, insertbackground=BLUE, relief="flat",
                        font=F, highlightthickness=1, highlightbackground=BORDER, highlightcolor=BLUE)

    def _spin(self, parent, lo, hi, width=5):
        return tk.Spinbox(parent, from_=lo, to=hi, width=width, bg=WHITE, fg=TEXT, relief="flat",
                          font=F, highlightthickness=1, highlightbackground=BORDER,
                          highlightcolor=BLUE, insertbackground=BLUE)

    def _sidebar(self, body):
        sb = tk.Frame(body, bg=WHITE, width=340, highlightbackground=BORDER, highlightthickness=1)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        tk.Label(sb, text="INPUT", bg=WHITE, fg=NAVY, font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=14, pady=(12, 2))
        tk.Label(sb, text="Processes", bg=WHITE, fg=MUTED, font=F_S).pack(anchor="w", padx=14)

        self.ptree = make_table(sb, ("pid", "at", "bt"), ("PROCESS ID", "ARRIVAL", "BURST"),
                                (110, 90, 90), 9)
        self.ptree.pack(fill="x", padx=14, pady=6)

        form = tk.Frame(sb, bg=WHITE)
        form.pack(fill="x", padx=14)
        for i, t in enumerate(("PID", "Arrival", "Burst")):
            tk.Label(form, text=t, bg=WHITE, fg=MUTED, font=F_S).grid(row=0, column=i, sticky="w")
        self.e_pid = self._entry(form, 8)
        self.e_at, self.e_bt = self._spin(form, 0, 999), self._spin(form, 1, 999)
        for col, w in enumerate((self.e_pid, self.e_at, self.e_bt)):
            w.grid(row=1, column=col, padx=(0, 6), ipady=3)
            w.bind("<Return>", lambda e: self.add_process())
        mkbtn(form, "＋ ADD", self.add_process, bg=GREEN, fg="white", hover="#25804a", pady=3).grid(row=1, column=3)

        row = tk.Frame(sb, bg=WHITE)
        row.pack(fill="x", padx=14, pady=8)
        for t, c in (("Remove", self.remove_selected), ("Clear", self.clear_all)):
            mkbtn(row, t, c, font=F_S, padx=10, pady=4).pack(side="left", padx=(0, 4))

        self.count_lbl = tk.Label(sb, text="", bg=WHITE, fg=BLUE, font=F_B)
        self.count_lbl.pack(anchor="w", padx=14)
        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=14, pady=10)

        qf = tk.Frame(sb, bg=WHITE)
        qf.pack(fill="x", padx=14)
        tk.Label(qf, text="Round Robin time quantum:", bg=WHITE, fg=BLUE, font=F_B).pack(side="left")
        self.e_q = self._spin(qf, 1, 99, 4)
        self.e_q.delete(0, "end")
        self.e_q.insert(0, "3")
        self.e_q.pack(side="right", ipady=3)

        self.err = tk.Label(sb, text="", bg=WHITE, fg="#d6336c", font=F_S, wraplength=300, justify="left")
        self.err.pack(anchor="w", padx=14, pady=(10, 0))
        mkbtn(sb, "▶  Run Simulation", self.run, bg=BLUE, fg="white", hover="#1d56c4",
              font=("Segoe UI", 12, "bold"), pady=11).pack(fill="x", padx=14, pady=(8, 6))

    def _next_pid(self):
        used = {r[0].upper() for r in self.rows}
        k = 1
        while f"P{k}" in used:
            k += 1
        return f"P{k}"

    def _refresh_inputs(self):
        self.ptree.delete(*self.ptree.get_children())
        for i, (pid, at, bt) in enumerate(self.rows):
            self.ptree.insert("", "end", iid=str(i), values=(pid, at, bt))
        self.count_lbl.config(text=f"Number of processes: {len(self.rows)}")
        self.e_pid.delete(0, "end")
        self.e_pid.insert(0, self._next_pid())

    def add_process(self):
        pid = self.e_pid.get().strip() or self._next_pid()
        try:
            at, bt = int(self.e_at.get()), int(self.e_bt.get())
        except ValueError:
            return self._error("Arrival and burst time must be whole numbers.")
        if pid.upper() == IDLE:
            return self._error("'IDLE' is reserved. Use another Process ID.")
        if any(r[0].upper() == pid.upper() for r in self.rows):
            return self._error(f"Process ID '{pid}' already exists.")
        if at < 0 or bt < 1:
            return self._error("Arrival must be ≥ 0 and burst must be ≥ 1.")
        if len(self.rows) >= 20:
            return self._error("Maximum of 20 processes.")
        self.rows.append((pid, at, bt))
        self._error("")
        self._refresh_inputs()

    def remove_selected(self):
        for i in sorted((int(i) for i in self.ptree.selection()), reverse=True):
            del self.rows[i]
        self._refresh_inputs()

    def clear_all(self):
        self.rows = []
        self._error("")
        self._refresh_inputs()

    def _error(self, msg):
        self.err.config(text=msg)

    def run(self):
        if not self.rows:
            return self._error("Add at least one process first.")
        try:
            q = int(self.e_q.get())
            if q < 1:
                raise ValueError
        except ValueError:
            return self._error("Time quantum must be a whole number ≥ 1.")
        self._error("")

        procs = [Process(pid, at, bt, i) for i, (pid, at, bt) in enumerate(self.rows)]
        colors = {p.pid: PASTEL[i % len(PASTEL)] for i, p in enumerate(procs)}
        results = [fcfs(procs), sjf(procs), srtf(procs), round_robin(procs, q)]

        for f in self.view_frames:
            f.destroy()
        self.view_frames = []
        for r in results:
            self._add_tab(f"  {r.key}  ", AlgoView(self.nb, colors, r))
        self._add_tab("  Compare  ", CompareView(self.nb, results))
        self.nb.select(0)

    def _add_tab(self, title, frame):
        self.nb.add(frame, text=title, padding=10)
        self.view_frames.append(frame)


if __name__ == "__main__":
    App().mainloop()
