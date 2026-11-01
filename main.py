"""Fitness and Diet Tracker - Tkinter window.

This file only builds the screen and connects each button to a method.
Validation and calculation are done in tracker.py and utils.py, and all
SQL is in database.py.
"""

import os
import tkinter as tk
from datetime import date, timedelta
from tkinter import filedialog, messagebox, ttk

from charts import build_progress_figure
from database import Database
from tracker import FitnessTracker
from utils import ACTIVITY_LEVELS, GENDERS, GOALS, MEAL_TYPES, kcal, validate_date

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fitness_tracker.db")
COLOURS = {"ok": "#2e7d32", "warning": "#e68a00", "over": "#c62828", "none": "#555555"}


class FitnessApp:
    def __init__(self, root, db_path=DB_FILE):
        self.root = root
        self.root.title("Fitness and Diet Tracker")
        self.root.geometry("1020x700")
        self.root.minsize(960, 660)
        self.db = Database(db_path)
        self.tracker = FitnessTracker(self.db)
        self.canvas = None
        self.figure = None

        self.make_variables()
        self.build_style()
        self.build_menu()
        self.build_summary_panel()
        self.build_tabs()
        self.status_var = tk.StringVar(value="Welcome. Save your profile to begin.")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken",
                  anchor="w", padding=3).pack(side="bottom", fill="x")

        self.load_profile_form()
        self.refresh_all()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # --------------------------------------------------------- set-up
    def make_variables(self):
        today = date.today().strftime("%d-%m-%Y")
        self.day_var = tk.StringVar(value=today)
        self.name_var = tk.StringVar()
        self.age_var = tk.StringVar()
        self.gender_var = tk.StringVar()
        self.height_var = tk.StringVar()
        self.weight_var = tk.StringVar()
        self.activity_var = tk.StringVar()
        self.goal_var = tk.StringVar()
        self.meal_type_var = tk.StringVar()
        self.food_var = tk.StringVar()
        self.food_info_var = tk.StringVar(value="Choose a food to see its calories.")
        self.servings_var = tk.StringVar(value="1")
        self.activity_name_var = tk.StringVar()
        self.minutes_var = tk.StringVar()
        self.wt_date_var = tk.StringVar(value=today)
        self.wt_value_var = tk.StringVar()
        self.fig_vars = {key: tk.StringVar(value="-") for key in
                         ("target", "eaten", "burned", "remaining")}
        self.percent_var = tk.StringVar(value="0% of target used")
        self.message_var = tk.StringVar()

    def build_style(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        for status, colour in COLOURS.items():
            style.configure(f"{status}.Horizontal.TProgressbar", background=colour)

    def build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Save Chart as Image...", command=self.save_chart)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    # ------------------------------------------------- daily summary panel
    def build_summary_panel(self):
        panel = ttk.LabelFrame(self.root, text="Daily Summary", padding=8)
        panel.pack(fill="x", padx=8, pady=(8, 4))

        row = ttk.Frame(panel)
        row.pack(fill="x")
        ttk.Label(row, text="Date (DD-MM-YYYY):").pack(side="left")
        ttk.Entry(row, textvariable=self.day_var, width=12).pack(side="left", padx=4)
        ttk.Button(row, text="Show", command=self.on_show_day).pack(side="left", padx=2)
        ttk.Button(row, text="< Previous Day", command=lambda: self.move_day(-1)).pack(side="left", padx=2)
        ttk.Button(row, text="Next Day >", command=lambda: self.move_day(1)).pack(side="left", padx=2)
        ttk.Button(row, text="Today", command=self.go_today).pack(side="left", padx=2)

        figures = ttk.Frame(panel)
        figures.pack(fill="x", pady=(8, 2))
        captions = [("target", "Daily Calorie Target"), ("eaten", "Calories Eaten"),
                    ("burned", "Calories Burned"), ("remaining", "Calories Remaining")]
        for column, (key, caption) in enumerate(captions):
            box = ttk.Frame(figures)
            box.grid(row=0, column=column, padx=22, sticky="w")
            ttk.Label(box, text=caption, foreground="#666666").pack(anchor="w")
            label = ttk.Label(box, textvariable=self.fig_vars[key], font=("Arial", 15, "bold"))
            label.pack(anchor="w")
            if key == "remaining":
                self.remaining_label = label

        bar_row = ttk.Frame(panel)
        bar_row.pack(fill="x", pady=(6, 0))
        self.progress = ttk.Progressbar(bar_row, maximum=100, length=600)
        self.progress.pack(side="left", fill="x", expand=True)
        ttk.Label(bar_row, textvariable=self.percent_var, width=22,
                  anchor="e").pack(side="left", padx=(8, 0))
        self.message_label = ttk.Label(panel, textvariable=self.message_var,
                                       font=("Arial", 10, "bold"))
        self.message_label.pack(anchor="w", pady=(4, 0))

    # ------------------------------------------------------------- tabs
    def build_tabs(self):
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=8, pady=4)
        self.build_profile_tab()
        self.build_meals_tab()
        self.build_workouts_tab()
        self.build_progress_tab()

    def build_profile_tab(self):
        tab = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(tab, text="Profile")
        form = ttk.LabelFrame(tab, text="Personal Details", padding=10)
        form.pack(side="left", anchor="n")
        rows = [
            ("Name:", ttk.Entry(form, textvariable=self.name_var, width=28)),
            ("Age (years):", ttk.Entry(form, textvariable=self.age_var, width=28)),
            ("Gender:", ttk.Combobox(form, textvariable=self.gender_var, values=GENDERS,
                                     state="readonly", width=25)),
            ("Height (cm):", ttk.Entry(form, textvariable=self.height_var, width=28)),
            ("Weight (kg):", ttk.Entry(form, textvariable=self.weight_var, width=28)),
            ("Activity level:", ttk.Combobox(form, textvariable=self.activity_var,
                                             values=list(ACTIVITY_LEVELS), state="readonly", width=25)),
            ("Goal:", ttk.Combobox(form, textvariable=self.goal_var, values=list(GOALS),
                                   state="readonly", width=25)),
        ]
        for r, (text, widget) in enumerate(rows):
            ttk.Label(form, text=text).grid(row=r, column=0, sticky="w", pady=4)
            widget.grid(row=r, column=1, padx=8, pady=4)
        ttk.Button(form, text="Save Profile", command=self.on_save_profile).grid(
            row=len(rows), column=0, columnspan=2, pady=(10, 0), sticky="ew")

        self.stats_frame = ttk.LabelFrame(tab, text="Your Health Numbers", padding=10)
        self.stats_frame.pack(side="left", anchor="n", padx=24, fill="y")
        self.stats_vars = {}
        for key, caption in [("bmi", "BMI"), ("category", "BMI category"),
                             ("bmr", "BMR (calories at rest)"), ("target", "Daily calorie target")]:
            self.stats_vars[key] = tk.StringVar(value="-")
            ttk.Label(self.stats_frame, text=caption, foreground="#666666").pack(anchor="w")
            ttk.Label(self.stats_frame, textvariable=self.stats_vars[key],
                      font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(self.stats_frame, justify="left", foreground="#666666", wraplength=230,
                  text="These are estimates for study purposes.\nThey are not medical advice."
                  ).pack(anchor="w", pady=(6, 0))

    def build_table(self, parent, columns):
        """A Treeview with a scroll bar. columns = [(name, width, anchor)]."""
        frame = ttk.Frame(parent)
        table = ttk.Treeview(frame, columns=[c[0] for c in columns], show="headings",
                             selectmode="browse", height=10)
        for name, width, anchor in columns:
            table.heading(name, text=name)
            table.column(name, width=width, anchor=anchor)
        bar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=bar.set)
        table.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        return frame, table

    def build_meals_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(tab, text="Meals")
        form = ttk.LabelFrame(tab, text="Add Meal", padding=10)
        form.pack(side="left", anchor="n")
        ttk.Label(form, text="Meal type:").pack(anchor="w")
        ttk.Combobox(form, textvariable=self.meal_type_var, values=MEAL_TYPES,
                     state="readonly", width=26).pack(pady=(0, 6))
        ttk.Label(form, text="Food:").pack(anchor="w")
        self.food_combo = ttk.Combobox(form, textvariable=self.food_var, state="readonly",
                                       values=[f[1] for f in self.db.get_foods()], width=26)
        self.food_combo.pack(pady=(0, 2))
        self.food_combo.bind("<<ComboboxSelected>>", self.on_food_selected)
        ttk.Label(form, textvariable=self.food_info_var, foreground="#666666",
                  wraplength=210).pack(anchor="w", pady=(0, 6))
        ttk.Label(form, text="Servings:").pack(anchor="w")
        ttk.Entry(form, textvariable=self.servings_var, width=28).pack(pady=(0, 10))
        ttk.Button(form, text="Add Meal", command=self.on_add_meal).pack(fill="x", pady=2)
        ttk.Button(form, text="Delete Selected", command=self.on_delete_meal).pack(fill="x", pady=2)
        ttk.Button(form, text="Clear Form", command=self.clear_meal_form).pack(fill="x", pady=2)

        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.meals_info_var = tk.StringVar()
        ttk.Label(right, textvariable=self.meals_info_var, anchor="e").pack(fill="x")
        frame, self.meal_table = self.build_table(right, [
            ("ID", 50, "center"), ("Meal", 100, "w"), ("Food", 230, "w"),
            ("Servings", 80, "center"), ("Calories", 100, "e")])
        frame.pack(fill="both", expand=True)
        self.meal_totals_var = tk.StringVar()
        ttk.Label(right, textvariable=self.meal_totals_var,
                  foreground="#444444").pack(fill="x", pady=(4, 0))

    def build_workouts_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(tab, text="Workouts")
        form = ttk.LabelFrame(tab, text="Add Workout", padding=10)
        form.pack(side="left", anchor="n")
        ttk.Label(form, text="Activity:").pack(anchor="w")
        ttk.Combobox(form, textvariable=self.activity_name_var, state="readonly",
                     values=[a[1] for a in self.db.get_activities()],
                     width=26).pack(pady=(0, 6))
        ttk.Label(form, text="Minutes:").pack(anchor="w")
        ttk.Entry(form, textvariable=self.minutes_var, width=28).pack(pady=(0, 10))
        ttk.Button(form, text="Add Workout", command=self.on_add_workout).pack(fill="x", pady=2)
        ttk.Button(form, text="Delete Selected", command=self.on_delete_workout).pack(fill="x", pady=2)
        ttk.Button(form, text="Clear Form", command=self.clear_workout_form).pack(fill="x", pady=2)
        ttk.Label(form, foreground="#666666", wraplength=210, justify="left",
                  text="Calories burned = MET x weight (kg) x time (hours).").pack(anchor="w", pady=(10, 0))

        right = ttk.Frame(tab)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.workouts_info_var = tk.StringVar()
        ttk.Label(right, textvariable=self.workouts_info_var, anchor="e").pack(fill="x")
        frame, self.workout_table = self.build_table(right, [
            ("ID", 50, "center"), ("Activity", 240, "w"),
            ("Minutes", 90, "center"), ("Calories Burned", 130, "e")])
        frame.pack(fill="both", expand=True)

    def build_progress_tab(self):
        tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(tab, text="Weight and Progress")
        top = ttk.Frame(tab)
        top.pack(fill="x")
        form = ttk.LabelFrame(top, text="Log Weight", padding=8)
        form.pack(side="left", anchor="n")
        ttk.Label(form, text="Date:").grid(row=0, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.wt_date_var, width=12).grid(row=0, column=1, padx=6)
        ttk.Label(form, text="Weight (kg):").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(form, textvariable=self.wt_value_var, width=12).grid(row=1, column=1, padx=6)
        ttk.Button(form, text="Save Weight", command=self.on_add_weight).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(4, 2))
        ttk.Button(form, text="Delete Selected", command=self.on_delete_weight).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=2)
        ttk.Button(form, text="Save Chart as Image", command=self.save_chart).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=2)
        frame, self.weight_table = self.build_table(top, [
            ("Date", 120, "center"), ("Weight (kg)", 110, "center")])
        self.weight_table.configure(height=6)
        frame.pack(side="left", fill="x", expand=True, padx=(12, 0))
        self.chart_frame = ttk.Frame(tab)
        self.chart_frame.pack(fill="both", expand=True, pady=(8, 0))

    # ------------------------------------------------------ small helpers
    def set_status(self, text):
        self.status_var.set(text)

    def report(self, ok, message):
        """Show a failure in a message box, or a success in the status bar."""
        if ok:
            self.set_status(message)
        else:
            messagebox.showerror("Invalid Input", message)
        return ok

    def current_day(self):
        ok, value = validate_date(self.day_var.get())
        if not ok:
            messagebox.showerror("Invalid Date", value)
            return None
        return value

    def selected_id(self, table):
        selection = table.selection()
        return selection[0] if selection else None

    # -------------------------------------------------------- navigation
    def on_show_day(self):
        if self.current_day() is not None:
            self.refresh_all()
            self.set_status(f"Showing {self.day_var.get().strip()}")

    def move_day(self, step):
        day = self.current_day()
        if day is None:
            return
        new_day = day + timedelta(days=step)
        if new_day > date.today():
            self.set_status("You cannot go beyond today.")
            return
        self.day_var.set(new_day.strftime("%d-%m-%Y"))
        self.refresh_all()

    def go_today(self):
        self.day_var.set(date.today().strftime("%d-%m-%Y"))
        self.refresh_all()

    # ----------------------------------------------------------- profile
    def load_profile_form(self):
        profile = self.db.get_profile()
        if profile is None:
            return
        self.name_var.set(profile["name"])
        self.age_var.set(str(profile["age"]))
        self.gender_var.set(profile["gender"])
        self.height_var.set(f"{profile['height_cm']:g}")
        self.activity_var.set(profile["activity"])
        self.goal_var.set(profile["goal"])
        weight = self.db.get_latest_weight()
        if weight is not None:
            self.weight_var.set(f"{weight:g}")

    def on_save_profile(self):
        ok, message = self.tracker.save_profile(
            self.name_var.get(), self.age_var.get(), self.gender_var.get(),
            self.height_var.get(), self.weight_var.get(),
            self.activity_var.get(), self.goal_var.get())
        if self.report(ok, message):
            self.refresh_all()

    # ------------------------------------------------------------- meals
    def on_food_selected(self, _event=None):
        food = self.db.get_food(self.food_var.get())
        if food:
            self.food_info_var.set(f"{food[2]:g} kcal per serving ({food[3]})")

    def clear_meal_form(self):
        self.meal_type_var.set("")
        self.food_var.set("")
        self.servings_var.set("1")
        self.food_info_var.set("Choose a food to see its calories.")

    def on_add_meal(self):
        ok, message = self.tracker.add_meal(
            self.day_var.get(), self.meal_type_var.get(),
            self.food_var.get(), self.servings_var.get())
        if self.report(ok, message):
            self.clear_meal_form()
            self.refresh_all()
            self.show_target_popup()

    def on_delete_meal(self):
        meal_id = self.selected_id(self.meal_table)
        if meal_id is not None and not messagebox.askyesno(
                "Confirm Delete", "Delete the selected meal?"):
            return
        ok, message = self.tracker.delete_meal(None if meal_id is None else int(meal_id))
        if self.report(ok, message):
            self.refresh_all()

    # ---------------------------------------------------------- workouts
    def clear_workout_form(self):
        self.activity_name_var.set("")
        self.minutes_var.set("")

    def on_add_workout(self):
        ok, message = self.tracker.add_workout(
            self.day_var.get(), self.activity_name_var.get(), self.minutes_var.get())
        if self.report(ok, message):
            self.clear_workout_form()
            self.refresh_all()

    def on_delete_workout(self):
        workout_id = self.selected_id(self.workout_table)
        if workout_id is not None and not messagebox.askyesno(
                "Confirm Delete", "Delete the selected workout?"):
            return
        ok, message = self.tracker.delete_workout(
            None if workout_id is None else int(workout_id))
        if self.report(ok, message):
            self.refresh_all()

    # ----------------------------------------------------------- weights
    def on_add_weight(self):
        ok, message = self.tracker.add_weight(self.wt_date_var.get(), self.wt_value_var.get())
        if self.report(ok, message):
            self.wt_value_var.set("")
            self.refresh_all()

    def on_delete_weight(self):
        iso = self.selected_id(self.weight_table)
        if iso is None:
            self.report(False, "Select a weight in the table first.")
            return
        day = date.fromisoformat(iso).strftime("%d-%m-%Y")
        ok, message = self.tracker.delete_weight(day)
        if self.report(ok, message):
            self.refresh_all()

    # ----------------------------------------------------------- refresh
    def refresh_all(self):
        day = self.current_day()
        if day is None:
            return
        summary = self.tracker.day_summary(day)
        self.refresh_summary(summary)
        self.refresh_meals(day, summary)
        self.refresh_workouts(day)
        self.refresh_weights()
        self.refresh_profile_stats()
        self.draw_chart(day)

    def refresh_summary(self, summary):
        status, text = self.tracker.day_message(summary)
        target = summary["target"]
        self.fig_vars["target"].set("-" if target is None else kcal(target))
        self.fig_vars["eaten"].set(kcal(summary["eaten"]))
        self.fig_vars["burned"].set(kcal(summary["burned"]))
        self.fig_vars["remaining"].set(
            "-" if summary["remaining"] is None else kcal(summary["remaining"]))
        self.percent_var.set(f"{summary['percent']:.0f}% of target used")
        self.progress.configure(value=min(summary["percent"], 100),
                                style=f"{status}.Horizontal.TProgressbar")
        self.message_var.set(text)
        self.message_label.configure(foreground=COLOURS[status])
        self.remaining_label.configure(foreground=COLOURS[status])

    def fill_table(self, table, rows):
        table.delete(*table.get_children())
        for iid, values in rows:
            table.insert("", "end", iid=str(iid), values=values)

    def refresh_meals(self, day, summary):
        meals = self.db.get_meals(day)
        self.fill_table(self.meal_table, [
            (m[0], (m[0], m[1], m[2], f"{m[3]:g}", f"{m[4]:,.0f} kcal")) for m in meals])
        self.meals_info_var.set(f"{len(meals)} item(s) on {day.strftime('%d-%m-%Y')}, "
                                f"total {kcal(summary['eaten'])}")
        self.meal_totals_var.set("   ".join(
            f"{name}: {kcal(total)}" for name, total in summary["meal_totals"]))

    def refresh_workouts(self, day):
        workouts = self.db.get_workouts(day)
        self.fill_table(self.workout_table, [
            (w[0], (w[0], w[1], w[2], f"{w[3]:,.0f} kcal")) for w in workouts])
        self.workouts_info_var.set(
            f"{len(workouts)} workout(s) on {day.strftime('%d-%m-%Y')}, "
            f"total {kcal(sum(w[3] for w in workouts))} burned")

    def refresh_weights(self):
        weights = self.db.get_weights()
        self.fill_table(self.weight_table, [
            (d, (date.fromisoformat(d).strftime("%d-%m-%Y"), f"{w:g}"))
            for d, w in reversed(weights)])

    def refresh_profile_stats(self):
        stats = self.tracker.profile_stats()
        values = {"bmi": "-", "category": "-", "bmr": "-", "target": "-"}
        if stats:
            values = {"bmi": f"{stats['bmi']}", "category": stats["category"],
                      "bmr": kcal(stats["bmr"]), "target": kcal(stats["target"])}
        for key, text in values.items():
            self.stats_vars[key].set(text)

    def show_target_popup(self):
        day = self.current_day()
        popup = self.tracker.popup_for(self.tracker.day_summary(day)) if day else None
        if popup is None:
            return
        kind, title, text = popup
        (messagebox.showerror if kind == "error" else messagebox.showwarning)(title, text)

    # ------------------------------------------------------------- chart
    def draw_chart(self, day):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        weights, daily, target = self.tracker.chart_data(day)
        self.figure = build_progress_figure(weights, daily, target)
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def save_chart(self):
        if self.figure is None:
            return
        path = filedialog.asksaveasfilename(
            title="Save chart", defaultextension=".png",
            filetypes=[("PNG image", "*.png")], initialfile="progress_chart.png")
        if path:
            self.figure.savefig(path, dpi=150)
            self.set_status(f"Chart saved to {path}")

    # -------------------------------------------------------------- misc
    def show_about(self):
        messagebox.showinfo(
            "About",
            "Fitness and Diet Tracker\nA BCA (Data Science) mini project.\n\n"
            "Calorie values are approximate. BMI, BMR and the daily target are\n"
            "estimates for study purposes and are not medical advice.")

    def on_close(self):
        self.db.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    FitnessApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
