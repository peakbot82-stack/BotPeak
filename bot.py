# bot.py - PREDICTOR BOT V8 COMPLETO (HACK + PRO + ANALISTA)
# HACK: Estrategia Anti-sistema (seguir color + ANTI tras 2 pérdidas)
# PRO: BASE + ALTERNANCIA + DOBLE/TRIPLE (corregido)
# ANALISTA: Motor estadístico compuesto (Markov + Momentum + Frecuencia + Alternancia + Hot/Cold)
# CON SISTEMA DE PAUSA, REINICIO, RECUPERACIÓN DE SALDO Y ARCHIVO PERSISTENTE

import json
import os
import threading
import time
import requests
import asyncio
import re
import sqlite3
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import Counter, defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== CONFIGURACIÓN ====================
BOT_TOKEN = "8758409892:AAElGrpay6Kw5MvRL1TBfQRcK4omW63iQSQ"
ADMIN_IDS = [8051843698]
ADMIN_GROUP_ID = -1003731875494
MY_WALLET_BEP20 = "0x621917958C7ac81190e9f876C23D6B9914f31263"

WIN_IMAGE_URL = "https://i.postimg.cc/T2pH8v1q/1777831023149.png"
TAKE_PROFIT_IMAGE_URL = "https://i.postimg.cc/Pf88n71y/1778974518057.png"

# ==================== PLANES DE LICENCIA ====================
LICENSE_PLANS = {
    "hack": {"price": 15, "days": 30, "max_users": 1, "name": "🔧 Hack 30 Días", "mode": "hack"},
    "pro": {"price": 60, "days": 90, "max_users": 1, "name": "🏆 PRO 90 Días", "mode": "pro"},
    "analista": {"price": 100, "days": 90, "max_users": 1, "name": "🔬 ANALISTA 90 Días", "mode": "analista"},
}


# ==================== ARCHIVO DE RESULTADOS (SQLite) ====================
class ResultArchive:
    """Almacena TODOS los resultados en SQLite para análisis persistente."""

    def __init__(self, db_file="results_archive.db"):
        self.db_file = db_file
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    color TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    period_id TEXT,
                    session_id TEXT,
                    metadata TEXT
                )
            """)
            c.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON results(timestamp)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_session ON results(session_id)")
            conn.commit()
            conn.close()

    def save_result(self, color: str, period_id: str = None,
                    session_id: str = None, metadata: dict = None):
        with self._lock:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute(
                "INSERT INTO results (color, timestamp, period_id, session_id, metadata) VALUES (?, ?, ?, ?, ?)",
                (color, datetime.now().isoformat(), period_id, session_id,
                 json.dumps(metadata) if metadata else None)
            )
            conn.commit()
            conn.close()

    def get_last_n(self, n: int = 100, session_id: str = None) -> List[str]:
        with self._lock:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            if session_id:
                c.execute(
                    "SELECT color FROM results WHERE session_id=? ORDER BY id DESC LIMIT ?",
                    (session_id, n))
            else:
                c.execute("SELECT color FROM results ORDER BY id DESC LIMIT ?", (n,))
            rows = c.fetchall()
            conn.close()
            return [r[0] for r in reversed(rows)]

    def get_all(self, session_id: str = None) -> List[str]:
        with self._lock:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            if session_id:
                c.execute("SELECT color FROM results WHERE session_id=? ORDER BY id", (session_id,))
            else:
                c.execute("SELECT color FROM results ORDER BY id")
            rows = c.fetchall()
            conn.close()
            return [r[0] for r in rows]

    def get_count(self, session_id: str = None) -> int:
        with self._lock:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            if session_id:
                c.execute("SELECT COUNT(*) FROM results WHERE session_id=?", (session_id,))
            else:
                c.execute("SELECT COUNT(*) FROM results")
            count = c.fetchone()[0]
            conn.close()
            return count

    def get_results_by_period(self, hours: int = 24) -> List[str]:
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        with self._lock:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("SELECT color FROM results WHERE timestamp >= ? ORDER BY id", (cutoff,))
            rows = c.fetchall()
            conn.close()
            return [r[0] for r in rows]

    def clear_all(self):
        with self._lock:
            conn = sqlite3.connect(self.db_file)
            c = conn.cursor()
            c.execute("DELETE FROM results")
            conn.commit()
            conn.close()


# ==================== ANALIZADOR DE PATRONES ====================
class PatternAnalyzer:
    """Analiza patrones estadísticos en los resultados archivados."""

    def __init__(self, archive: ResultArchive):
        self.archive = archive

    def frequency_analysis(self, data: List[str] = None, n: int = 200) -> Dict:
        if data is None:
            data = self.archive.get_last_n(n)
        if not data:
            return {"error": "Sin datos", "count": 0}
        total = len(data)
        counter = Counter(data)
        red_count = counter.get('red', 0)
        blue_count = counter.get('blue', 0)
        red_pct = (red_count / total) * 100 if total > 0 else 0
        blue_pct = (blue_count / total) * 100 if total > 0 else 0
        std_dev = math.sqrt(0.5 * 0.5 / total) * 100 if total > 0 else 0
        deviation = abs(red_pct - 50)
        z_score = deviation / std_dev if std_dev > 0 else 0
        significant = z_score > 1.96
        return {
            "total": total, "red": red_count, "blue": blue_count,
            "red_pct": round(red_pct, 1), "blue_pct": round(blue_pct, 1),
            "deviation": round(deviation, 1), "z_score": round(z_score, 2),
            "significant": significant,
            "underdog": "red" if red_pct < blue_pct else "blue",
            "underdog_deficit": round(abs(red_pct - blue_pct), 1)
        }

    def streak_analysis(self, data: List[str] = None, n: int = 300) -> Dict:
        if data is None:
            data = self.archive.get_last_n(n)
        if len(data) < 5:
            return {"error": "Sin datos", "count": len(data)}
        streaks = []
        current_color = data[0]
        current_length = 1
        for i in range(1, len(data)):
            if data[i] == current_color:
                current_length += 1
            else:
                streaks.append({"color": current_color, "length": current_length})
                current_color = data[i]
                current_length = 1
        streaks.append({"color": current_color, "length": current_length})
        lengths = [s["length"] for s in streaks]
        red_streaks = [s["length"] for s in streaks if s["color"] == "red"]
        blue_streaks = [s["length"] for s in streaks if s["color"] == "blue"]
        return {
            "total_streaks": len(streaks),
            "avg_length": round(sum(lengths) / len(lengths), 2) if lengths else 0,
            "max_length": max(lengths) if lengths else 0,
            "min_length": min(lengths) if lengths else 0,
            "current_streak": streaks[-1] if streaks else None,
            "red_avg_streak": round(sum(red_streaks) / len(red_streaks), 2) if red_streaks else 0,
            "blue_avg_streak": round(sum(blue_streaks) / len(blue_streaks), 2) if blue_streaks else 0,
            "streak_distribution": dict(Counter(lengths)),
            "last_5_streaks": streaks[-5:]
        }

    def markov_chain(self, data: List[str] = None, n: int = 500, order: int = 2) -> Dict:
        if data is None:
            data = self.archive.get_last_n(n)
        if len(data) < order + 10:
            return {"error": "Sin datos", "count": len(data)}
        transitions = defaultdict(lambda: {"red": 0, "blue": 0})
        for i in range(order, len(data)):
            state = tuple(data[i - order:i])
            next_color = data[i]
            transitions[state][next_color] += 1
        probabilities = {}
        for state, counts in transitions.items():
            total = counts["red"] + counts["blue"]
            if total > 0:
                probabilities[state] = {
                    "red": round(counts["red"] / total, 4),
                    "blue": round(counts["blue"] / total, 4),
                    "total_observations": total,
                    "dominant": "red" if counts["red"] > counts["blue"] else "blue"
                    if counts["blue"] > counts["red"] else "equal"
                }
        current_state = tuple(data[-order:])
        current_probs = probabilities.get(current_state, None)
        return {
            "order": order, "total_states": len(probabilities),
            "current_state": list(current_state),
            "current_prediction": current_probs,
            "all_states": {str(k): v for k, v in
                           sorted(probabilities.items(),
                                  key=lambda x: x[1]["total_observations"],
                                  reverse=True)[:20]}
        }

    def alternation_analysis(self, data: List[str] = None, n: int = 200) -> Dict:
        if data is None:
            data = self.archive.get_last_n(n)
        if len(data) < 10:
            return {"error": "Sin datos"}
        changes = 0
        stays = 0
        for i in range(1, len(data)):
            if data[i] != data[i - 1]:
                changes += 1
            else:
                stays += 1
        total = changes + stays
        change_pct = (changes / total) * 100 if total > 0 else 0
        patterns_3 = Counter()
        for i in range(2, len(data)):
            p = f"{data[i-2][0].upper()}{data[i-1][0].upper()}{data[i][0].upper()}"
            patterns_3[p] += 1
        patterns_4 = Counter()
        for i in range(3, len(data)):
            p = f"{data[i-3][0].upper()}{data[i-2][0].upper()}{data[i-1][0].upper()}{data[i][0].upper()}"
            patterns_4[p] += 1
        return {
            "alternation_pct": round(change_pct, 1),
            "continuity_pct": round(100 - change_pct, 1),
            "total_changes": changes, "total_stays": stays,
            "tends_to": "ALTERNANCIA" if change_pct > 55 else "CONTINUIDAD" if change_pct < 45 else "EQUILIBRADO",
            "top_patterns_3": dict(patterns_3.most_common(8)),
            "top_patterns_4": dict(patterns_4.most_common(8)),
            "last_pattern_3": ''.join([c[0].upper() for c in data[-3:]]) if len(data) >= 3 else None,
            "last_pattern_4": ''.join([c[0].upper() for c in data[-4:]]) if len(data) >= 4 else None
        }

    def hot_cold_analysis(self, data: List[str] = None, window: int = 20, n: int = 200) -> Dict:
        if data is None:
            data = self.archive.get_last_n(n)
        if len(data) < window:
            return {"error": "Sin datos"}
        windows = []
        for i in range(0, len(data) - window + 1, window):
            segment = data[i:i + window]
            red_count = segment.count('red')
            windows.append({
                "start_idx": i, "red": red_count,
                "blue": window - red_count,
                "dominant": "red" if red_count > window / 2 else "blue"
            })
        current = data[-window:]
        current_red = current.count('red')
        current_blue = window - current_red
        recent_windows = windows[-3:] if len(windows) >= 3 else windows
        red_trend = [w["red"] for w in recent_windows]
        if len(red_trend) >= 2:
            if red_trend[-1] > red_trend[-2]:
                trend = "RED_CRECE"
            elif red_trend[-1] < red_trend[-2]:
                trend = "BLUE_CRECE"
            else:
                trend = "ESTABLE"
        else:
            trend = "INSUFICIENTE"
        return {
            "window_size": window, "current_red": current_red,
            "current_blue": current_blue,
            "current_dominant": "red" if current_red > current_blue else "blue",
            "trend": trend, "windows_total": len(windows),
            "last_3_windows": recent_windows
        }

    def momentum_analysis(self, data: List[str] = None, n: int = 100) -> Dict:
        if data is None:
            data = self.archive.get_last_n(n)
        if len(data) < 20:
            return {"error": "Sin datos"}
        continuation = 0
        reversal = 0
        for i in range(3, len(data)):
            if data[i-1] == data[i-2] == data[i-3]:
                if data[i] == data[i-1]:
                    continuation += 1
                else:
                    reversal += 1
        total_momentum = continuation + reversal
        if total_momentum == 0:
            return {"signal": "INSUFICIENTE", "samples": 0}
        cont_pct = (continuation / total_momentum) * 100
        alt_continuation = 0
        alt_reversal = 0
        for i in range(3, len(data)):
            if data[i-1] != data[i-2] and data[i-2] != data[i-3]:
                if data[i] != data[i-1]:
                    alt_continuation += 1
                else:
                    alt_reversal += 1
        total_alt = alt_continuation + alt_reversal
        alt_cont_pct = (alt_continuation / total_alt) * 100 if total_alt > 0 else 0
        return {
            "streak_samples": total_momentum,
            "streak_continuation_pct": round(cont_pct, 1),
            "streak_reversal_pct": round(100 - cont_pct, 1),
            "streak_signal": "MOMENTUM" if cont_pct > 55 else "REVERSION" if cont_pct < 45 else "NEUTRAL",
            "alternation_samples": total_alt,
            "alternation_continuation_pct": round(alt_cont_pct, 1),
            "alternation_signal": "MOMENTUM" if alt_cont_pct > 55 else "REVERSION" if alt_cont_pct < 45 else "NEUTRAL"
        }


# ==================== LICENCIA MANAGER ====================
class LicenseManager:
    def __init__(self, db_file="licenses.json"):
        self.db_file = db_file
        self.licenses = {}
        self.load()

    def load(self):
        if os.path.exists(self.db_file):
            try:
                with open(self.db_file, 'r') as f:
                    self.licenses = json.load(f)
            except:
                self.licenses = {}

    def save(self):
        try:
            with open(self.db_file, 'w') as f:
                json.dump(self.licenses, f, indent=2, default=str)
        except:
            pass

    def activate_license(self, user_id: int, plan: str) -> bool:
        if plan not in LICENSE_PLANS:
            return False
        plan_config = LICENSE_PLANS[plan]
        expiry_date = datetime.now() + timedelta(days=plan_config["days"])
        self.licenses[str(user_id)] = {
            "user_id": user_id, "plan": plan,
            "activated": datetime.now().isoformat(),
            "expiry": expiry_date.isoformat(),
            "max_users": plan_config["max_users"],
            "active": True, "mode": plan_config["mode"]
        }
        self.save()
        return True

    def check_license(self, user_id: int) -> Dict:
        license_data = self.licenses.get(str(user_id))
        if not license_data:
            return {"valid": False, "reason": "Sin licencia"}
        if not license_data.get("active", False):
            return {"valid": False, "reason": "Licencia inactiva"}
        expiry = datetime.fromisoformat(license_data["expiry"])
        if datetime.now() > expiry:
            license_data["active"] = False
            self.save()
            return {"valid": False, "reason": "Licencia expirada"}
        return {"valid": True, "data": license_data}

    def get_remaining_days(self, user_id: int) -> int:
        license_data = self.licenses.get(str(user_id))
        if not license_data:
            return 0
        expiry = datetime.fromisoformat(license_data["expiry"])
        return max(0, (expiry - datetime.now()).days)


# ==================== USER ACCOUNT ====================
class UserAccount:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.token = None
        self.device_id = None
        self.balance = 0.0
        self.logged_in = False
        self.initial_bet = 0.1
        self.initial_bet_original = 0.1
        self.current_bet = 0.1
        self.max_consecutive_losses = 5
        self.max_bet = 10.0
        self.consecutive_losses = 0
        self.wins = 0
        self.losses = 0
        self.betting_active = True
        self.use_martingale = False
        self.initial_balance_snapshot = 0.0
        self.take_profit_amount = 0.0
        self.paused = False
        self.restart_bet = 0.1
        self.waiting_for_win = False
        self.max_pauses = 2
        self.current_pauses = 0
        self.saldo_inicial_pausa = 0.0
        self.saldo_perdido = 0.0
        self.saldo_recuperado = False
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Android 10; Mobile)",
            "Accept-Language": "es-ES,es;q=0.9",
        })

    def login(self):
        import random
        self.device_id = ''.join(random.choices('0123456789', k=20))
        url = "https://www.ff2016.vip/api/user/login?lang=es"
        payload = {"account": self.username, "password": self.password, "deviceId": self.device_id}
        try:
            response = self.session.post(url, json=payload, timeout=10)
            data = response.json()
            if data.get("code") == 1:
                self.token = data["data"]["userinfo"]["token"]
                self.session.headers.update({"token": self.token})
                self.logged_in = True
                self.get_balance()
                return True, f"✅ Login OK | Balance: ${self.balance:.2f}"
            return False, data.get("msg", "Error de login")
        except Exception as e:
            return False, f"Error: {str(e)}"

    def get_balance(self):
        if not self.token:
            return False, "Login first"
        url = "https://www.ff2016.vip/api/user/get_user_info?lang=es"
        payload = {"deviceId": self.device_id}
        try:
            response = self.session.post(url, json=payload, timeout=10)
            data = response.json()
            if data.get("code") == 1:
                self.balance = float(data["data"].get("money", 0.0))
                return True, self.balance
            return False, data.get("msg")
        except Exception as e:
            return False, str(e)

    def place_bet(self, side, amount):
        if not self.token:
            return False, "Login first"
        if self.balance < amount:
            return False, f"Saldo insuficiente: ${self.balance:.2f}"
        url = "https://www.ff2016.vip/api/game/add_bet?lang=es"
        payload = {"side": side.lower(), "money": round(float(amount), 2), "redeem_id": 0, "deviceId": self.device_id}
        try:
            response = self.session.post(url, json=payload, timeout=10)
            data = response.json()
            if data.get("code") == 1:
                self.get_balance()
                return True, f"✅ ${amount:.2f} a {side.upper()} | Saldo: ${self.balance:.2f}"
            return False, data.get("msg", "Error en apuesta")
        except Exception as e:
            return False, str(e)

    def reset_bet(self):
        self.current_bet = self.initial_bet
        self.consecutive_losses = 0

    def update_bet_on_loss(self):
        self.consecutive_losses += 1
        if self.use_martingale:
            new_bet = min(self.current_bet * 2, self.max_bet)
            self.current_bet = new_bet
            return f"Martingale (x2): ${new_bet:.2f}"
        else:
            new_bet = min((self.current_bet * 2) + self.initial_bet, self.max_bet)
            self.current_bet = new_bet
            return f"Agresivo (x2+inicial): ${new_bet:.2f}"

    def check_take_profit(self) -> bool:
        if self.take_profit_amount <= 0 or self.initial_balance_snapshot <= 0:
            return False
        return (self.balance - self.initial_balance_snapshot) >= self.take_profit_amount

    def get_profit_info(self) -> str:
        if self.initial_balance_snapshot <= 0:
            return "Sin snapshot inicial"
        profit = self.balance - self.initial_balance_snapshot
        return f"💰 Inicial: ${self.initial_balance_snapshot:.2f} | Actual: ${self.balance:.2f} | Ganancia: ${profit:.2f}"

    def activate_pause(self) -> bool:
        if self.current_pauses >= self.max_pauses:
            return False
        self.paused = True
        self.waiting_for_win = True
        self.current_pauses += 1
        self.saldo_inicial_pausa = self.balance
        self.saldo_perdido = 0
        self.saldo_recuperado = False
        self.betting_active = False
        return True

    def reactivate_from_pause(self) -> bool:
        if not self.paused:
            return False
        self.paused = False
        self.waiting_for_win = False
        self.current_bet = self.restart_bet
        self.initial_bet = self.restart_bet
        self.consecutive_losses = 0
        self.betting_active = True
        self.saldo_recuperado = False
        self.saldo_perdido = self.saldo_inicial_pausa - self.balance if self.saldo_inicial_pausa > 0 else 0
        return True

    def check_saldo_recuperado(self) -> bool:
        if self.saldo_perdido <= 0:
            return False
        ganancia_actual = self.balance - self.saldo_inicial_pausa
        if ganancia_actual >= self.saldo_perdido:
            self.saldo_recuperado = True
            self.current_bet = self.initial_bet_original
            self.initial_bet = self.initial_bet_original
            return True
        return False

    def check_stop_loss(self) -> str:
        if self.consecutive_losses >= self.max_consecutive_losses:
            if self.current_pauses < self.max_pauses:
                return "PAUSAR"
            else:
                return "DETENER"
        return "CONTINUAR"

    def reset_pause_system(self):
        self.paused = False
        self.waiting_for_win = False
        self.current_pauses = 0
        self.saldo_inicial_pausa = 0.0
        self.saldo_perdido = 0.0
        self.saldo_recuperado = False
        self.betting_active = True
        self.current_bet = self.initial_bet_original
        self.initial_bet = self.initial_bet_original
        self.consecutive_losses = 0


# ==================== PREDICTOR HACK ====================
class HackPredictor:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.session_history = []
        self.last_prediction = None
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.anti_mode = False
        self.anti_rounds_left = 0
        self.anti_color = None
        self.first_lost_color = None
        self.second_lost_color = None
        self.active = True
        self.on_prediction = None
        self.on_result = None
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None

    def _normalizar_color(self, color: str) -> str:
        if color is None:
            return 'red'
        c = str(color).strip().lower()
        if c in ['red', 'rojo', 'r', '1', '🔴']:
            return 'red'
        if c in ['blue', 'azul', 'b', '2', '🔵']:
            return 'blue'
        try:
            return 'red' if int(c) == 1 else 'blue'
        except:
            pass
        return 'red'

    def process_color(self, color: str):
        if not self.active:
            return
        color = self._normalizar_color(color)
        if self.apuesta_pendiente and self.prediccion_pendiente is not None:
            is_win = (self.prediccion_pendiente == color)
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN (HACK)", True)
                    self.consecutive_wins += 1
                    self.consecutive_losses = 0
                    if self.anti_mode:
                        self.anti_mode = False
                        self.anti_rounds_left = 0
                        self.anti_color = None
                        self.first_lost_color = None
                        self.second_lost_color = None
                else:
                    self.on_result(f"❌ LOSS (HACK)", False)
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0
            self.apuesta_pendiente = False
            self.prediccion_pendiente = None
            return
        self.session_history.append(color)
        if len(self.session_history) > 20:
            self.session_history = self.session_history[-20:]
        if self.anti_mode:
            if self.anti_rounds_left > 0:
                prediccion = self.anti_color
                self.anti_rounds_left -= 1
                self.prediccion_pendiente = prediccion
                self.apuesta_pendiente = True
                self.last_prediction = prediccion
                if self.on_prediction:
                    rounds_done = 2 - self.anti_rounds_left
                    self.on_prediction(f"🛡️ MODO ANTI ({rounds_done}/2): {'🔴' if self.anti_color == 'red' else '🔵'}")
                return
        if not self.anti_mode:
            if self.consecutive_losses == 1:
                self.first_lost_color = color
            elif self.consecutive_losses == 2:
                self.second_lost_color = color
                self.anti_mode = True
                self.anti_rounds_left = 2
                self.anti_color = 'blue' if self.second_lost_color == 'red' else 'red'
                self.first_lost_color = None
                self.second_lost_color = None
                if self.on_prediction:
                    self.on_prediction(f"⚠️ 2 PÉRDIDAS CONSECUTIVAS - Activando MODO ANTI")
                prediccion = self.anti_color
                self.prediccion_pendiente = prediccion
                self.apuesta_pendiente = True
                self.last_prediction = prediccion
                self.anti_rounds_left -= 1
                if self.on_prediction:
                    self.on_prediction(f"🛡️ MODO ANTI (1/2): {'🔴' if self.anti_color == 'red' else '🔵'}")
                return
        if self.session_history:
            last_color = self.session_history[-1]
            self.prediccion_pendiente = last_color
            self.apuesta_pendiente = True
            self.last_prediction = last_color
            if self.on_prediction:
                self.on_prediction(f"🎯 HACK (BASE → {self._color_emoji(last_color)})")

    def _color_emoji(self, color: str) -> str:
        return "🔴" if color == 'red' else "🔵"

    def get_last_prediction(self) -> str:
        return self.last_prediction

    def reset(self):
        self.session_history = []
        self.last_prediction = None
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.anti_mode = False
        self.anti_rounds_left = 0
        self.anti_color = None
        self.first_lost_color = None
        self.second_lost_color = None
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None


# ==================== PREDICTOR PRO ====================
class ProPredictor:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.active = True
        self.on_prediction = None
        self.on_result = None
        self.session_history = []
        self.last_prediction = None
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None
        self.modo_actual = "BASE"
        self.patron_color = None
        self.alternancia_activa = False

    def _normalizar_color(self, color: str) -> str:
        if color is None:
            return 'red'
        c = str(color).strip().lower()
        if c in ['red', 'rojo', 'r', '1', '🔴']:
            return 'red'
        if c in ['blue', 'azul', 'b', '2', '🔵']:
            return 'blue'
        try:
            return 'red' if int(c) == 1 else 'blue'
        except:
            pass
        return 'red'

    def _color_emoji(self, color: str) -> str:
        return "🔴" if color == 'red' else "🔵"

    def _color_contrario(self, color: str) -> str:
        return 'blue' if color == 'red' else 'red'

    def _check_alternancia(self, colores) -> bool:
        if len(colores) < 3:
            return False
        return colores[-1] != colores[-2] and colores[-2] != colores[-3]

    def _get_color_alternancia(self, colores) -> str:
        if len(colores) < 2:
            return colores[-1] if colores else 'red'
        return self._color_contrario(colores[-1])

    def process_color(self, color: str):
        if not self.active:
            return
        color = self._normalizar_color(color)
        if self.apuesta_pendiente and self.prediccion_pendiente is not None:
            is_win = (self.prediccion_pendiente == color)
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN (PRO)", True)
                    self.consecutive_wins += 1
                    self.consecutive_losses = 0
                else:
                    self.on_result(f"❌ LOSS (PRO)", False)
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0
                if self.modo_actual == "TRIPLE":
                    self.modo_actual = "BASE"
                    self.patron_color = None
                    self.session_history = []
                    if self.on_prediction:
                        msg_t = "WIN" if is_win else "LOSS"
                        self.on_prediction(f"🔄 PRO: TRIPLE {msg_t} → Volviendo a BASE")
                elif self.modo_actual == "DOBLE" and is_win:
                    self.modo_actual = "BASE"
                    self.patron_color = None
                    self.session_history = []
                    if self.on_prediction:
                        self.on_prediction(f"🔄 PRO: DOBLE WIN → Volviendo a BASE")
                elif self.modo_actual == "DOBLE" and not is_win:
                    self.modo_actual = "TRIPLE"
                    if self.on_prediction:
                        self.on_prediction(f"🔄 PRO: DOBLE LOSS → TRIPLE")
                elif self.modo_actual == "ALTERNANCIA" and is_win:
                    self.alternancia_activa = True
                elif self.modo_actual == "ALTERNANCIA" and not is_win:
                    self.modo_actual = "DOBLE"
                    self.alternancia_activa = False
                    self.patron_color = color
                    if self.on_prediction:
                        self.on_prediction(f"🔄 PRO: ALTERNANCIA rota → DOBLE detectado!")
            self.apuesta_pendiente = False
            self.prediccion_pendiente = None
            return
        self.session_history.append(color)
        if len(self.session_history) > 20:
            self.session_history = self.session_history[-20:]
        if len(self.session_history) < 2:
            return
        prediccion = None
        patron_detectado = "BASE"
        if self.modo_actual == "TRIPLE":
            prediccion = self._color_contrario(self.session_history[-1])
            patron_detectado = "TRIPLE"
        elif self.modo_actual == "DOBLE":
            prediccion = self._color_contrario(self.session_history[-1])
            patron_detectado = "DOBLE"
        elif self.modo_actual == "ALTERNANCIA" and self.alternancia_activa:
            if self._check_alternancia(self.session_history):
                prediccion = self._get_color_alternancia(self.session_history)
                patron_detectado = "ALTERNANCIA"
            else:
                self.modo_actual = "DOBLE"
                self.alternancia_activa = False
                prediccion = self._color_contrario(self.session_history[-1])
                patron_detectado = "DOBLE"
                if self.on_prediction:
                    self.on_prediction(f"🔄 PRO: ALTERNANCIA rota → DOBLE detectado!")
        else:
            if self._check_alternancia(self.session_history):
                self.modo_actual = "ALTERNANCIA"
                self.alternancia_activa = True
                prediccion = self._get_color_alternancia(self.session_history)
                patron_detectado = "ALTERNANCIA"
            else:
                self.modo_actual = "BASE"
                prediccion = self.session_history[-1]
                patron_detectado = "BASE"
        if prediccion is None:
            prediccion = self.session_history[-1] if self.session_history else None
            patron_detectado = "BASE"
        if prediccion is None:
            return
        self.prediccion_pendiente = prediccion
        self.apuesta_pendiente = True
        self.last_prediction = prediccion
        emoji = self._color_emoji(prediccion)
        if self.on_prediction:
            if patron_detectado == "TRIPLE":
                cp = self.session_history[-1]
                self.on_prediction(f"🎯 PRO (TRIPLE {self._color_emoji(cp)}{self._color_emoji(cp)}{self._color_emoji(cp)} → {emoji})")
            elif patron_detectado == "DOBLE":
                cp = self.session_history[-1]
                self.on_prediction(f"🎯 PRO (DOBLE {self._color_emoji(cp)}{self._color_emoji(cp)} → {emoji})")
            elif patron_detectado == "ALTERNANCIA":
                self.on_prediction(f"🎯 PRO (ALTERNANCIA → {emoji})")
            else:
                self.on_prediction(f"🎯 PRO (BASE → {emoji})")

    def reset(self):
        self.session_history = []
        self.last_prediction = None
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.modo_actual = "BASE"
        self.patron_color = None
        self.alternancia_activa = False
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None


# ==================== PREDICTOR ANALISTA ====================
class AnalystPredictor:
    """Motor estadístico compuesto. Combina Markov, Momentum, Frecuencia, Alternancia y Hot/Cold."""

    def __init__(self, user_id: int, archive: ResultArchive):
        self.user_id = user_id
        self.archive = archive
        self.analyzer = PatternAnalyzer(archive)
        self.active = True
        self.on_prediction = None
        self.on_result = None
        self.last_prediction = None
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None
        self.min_data = 30
        self.warmup_mode = True
        self.weights = {
            "markov": 0.30,
            "momentum": 0.20,
            "frequency": 0.20,
            "alternation": 0.15,
            "hot_cold": 0.15
        }
        self.predictions_made = 0
        self.predictions_correct = 0

    def _color_emoji(self, color: str) -> str:
        return "🔴" if color == 'red' else "🔵"

    def _normalize(self, color: str) -> str:
        c = str(color).strip().lower()
        if c in ['red', 'rojo', 'r', '1']:
            return 'red'
        if c in ['blue', 'azul', 'b', '2']:
            return 'blue'
        try:
            return 'red' if int(c) == 1 else 'blue'
        except:
            pass
        return 'red'

    def _generate_prediction(self) -> Tuple[str, Dict]:
        data = self.archive.get_last_n(500)
        signals = {}
        scores = {"red": 0.0, "blue": 0.0}

        # SEÑAL 1: Markov orden 2
        try:
            markov = self.analyzer.markov_chain(data, n=500, order=2)
            if markov.get("current_prediction"):
                pred = markov["current_prediction"]
                conf = max(pred["red"], pred["blue"])
                if pred["red"] > pred["blue"]:
                    scores["red"] += self.weights["markov"] * conf
                else:
                    scores["blue"] += self.weights["markov"] * conf
                signals["markov"] = {"prediction": pred["dominant"], "confidence": round(conf * 100, 1), "state": markov["current_state"]}
        except:
            pass

        # SEÑAL 2: Markov orden 3
        try:
            markov3 = self.analyzer.markov_chain(data, n=500, order=3)
            if markov3.get("current_prediction"):
                pred = markov3["current_prediction"]
                conf = max(pred["red"], pred["blue"])
                if pred["red"] > pred["blue"]:
                    scores["red"] += 0.15 * conf
                else:
                    scores["blue"] += 0.15 * conf
                signals["markov3"] = {"prediction": pred["dominant"], "confidence": round(conf * 100, 1)}
        except:
            pass

        # SEÑAL 3: Momentum
        try:
            momentum = self.analyzer.momentum_analysis(data, n=100)
            if momentum.get("streak_samples", 0) > 5:
                last = data[-1] if data else None
                if momentum["streak_signal"] == "MOMENTUM":
                    scores[last] += self.weights["momentum"] * 0.6
                    signals["momentum"] = {"prediction": last, "signal": "SEGUIR"}
                elif momentum["streak_signal"] == "REVERSION":
                    opposite = 'blue' if last == 'red' else 'red'
                    scores[opposite] += self.weights["momentum"] * 0.6
                    signals["momentum"] = {"prediction": opposite, "signal": "REVERTIR"}
        except:
            pass

        # SEÑAL 4: Frecuencia
        try:
            freq = self.analyzer.frequency_analysis(data, n=200)
            if freq.get("significant") and freq.get("underdog_deficit", 0) > 3:
                underdog = freq["underdog"]
                strength = min(freq["underdog_deficit"] / 10, 1.0)
                scores[underdog] += self.weights["frequency"] * strength
                signals["frequency"] = {"prediction": underdog, "deficit": freq["underdog_deficit"], "z_score": freq["z_score"]}
        except:
            pass

        # SEÑAL 5: Alternancia
        try:
            alt = self.analyzer.alternation_analysis(data, n=200)
            if alt.get("alternation_pct", 50) > 58:
                last = data[-1] if data else None
                opposite = 'blue' if last == 'red' else 'red'
                strength = (alt["alternation_pct"] - 50) / 50
                scores[opposite] += self.weights["alternation"] * strength
                signals["alternation"] = {"prediction": opposite, "pct": alt["alternation_pct"], "signal": "ALTA_ALTERNANCIA"}
            elif alt.get("continuity_pct", 50) > 58:
                last = data[-1] if data else None
                strength = (alt["continuity_pct"] - 50) / 50
                scores[last] += self.weights["alternation"] * strength
                signals["alternation"] = {"prediction": last, "pct": alt["continuity_pct"], "signal": "ALTA_CONTINUIDAD"}
        except:
            pass

        # SEÑAL 6: Hot/Cold
        try:
            hc = self.analyzer.hot_cold_analysis(data, window=15, n=200)
            if hc.get("trend") == "RED_CRECE":
                scores["red"] += self.weights["hot_cold"] * 0.5
                signals["hot_cold"] = {"prediction": "red", "trend": hc["trend"]}
            elif hc.get("trend") == "BLUE_CRECE":
                scores["blue"] += self.weights["hot_cold"] * 0.5
                signals["hot_cold"] = {"prediction": "blue", "trend": hc["trend"]}
        except:
            pass

        # DECISIÓN FINAL
        total_score = scores["red"] + scores["blue"]
        if total_score == 0:
            prediction = data[-1] if data else 'red'
            confidence = 50.0
        else:
            if scores["red"] > scores["blue"]:
                prediction = "red"
                confidence = (scores["red"] / total_score) * 100
            else:
                prediction = "blue"
                confidence = (scores["blue"] / total_score) * 100

        return prediction, {
            "prediction": prediction, "confidence": round(confidence, 1),
            "scores": {"red": round(scores["red"], 3), "blue": round(scores["blue"], 3)},
            "signals": signals, "data_points": len(data), "warmup": self.warmup_mode
        }

    def process_color(self, color: str):
        if not self.active:
            return
        color = self._normalize(color)

        if self.apuesta_pendiente and self.prediccion_pendiente is not None:
            is_win = (self.prediccion_pendiente == color)
            self.predictions_made += 1
            if is_win:
                self.predictions_correct += 1
            if self.on_result:
                accuracy = (self.predictions_correct / self.predictions_made * 100 if self.predictions_made > 0 else 0)
                if is_win:
                    self.on_result(f"✅ WIN (ANALISTA) | Precisión: {accuracy:.1f}% ({self.predictions_correct}/{self.predictions_made})", True)
                else:
                    self.on_result(f"❌ LOSS (ANALISTA) | Precisión: {accuracy:.1f}% ({self.predictions_correct}/{self.predictions_made})", False)
            self.apuesta_pendiente = False
            self.prediccion_pendiente = None
            return

        self.archive.save_result(color, session_id=f"user_{self.user_id}")

        total = self.archive.get_count()
        if total < self.min_data:
            remaining = self.min_data - total
            if self.on_prediction:
                self.on_prediction(f"📊 RECOLECTANDO DATOS ({total}/{self.min_data}) - Faltan {remaining} rondas")
            return

        if self.warmup_mode and total >= self.min_data:
            self.warmup_mode = False
            if self.on_prediction:
                self.on_prediction(f"✅ DATOS SUFICIENTES ({total}) - ¡Analista activado!")

        prediction, details = self._generate_prediction()
        self.prediccion_pendiente = prediction
        self.apuesta_pendiente = True
        self.last_prediction = prediction

        if self.on_prediction:
            emoji = self._color_emoji(prediction)
            conf = details["confidence"]
            signals_count = len(details["signals"])
            if conf >= 65:
                conf_label = "🟢 ALTA"
            elif conf >= 55:
                conf_label = "🟡 MEDIA"
            else:
                conf_label = "🔴 BAJA"

            msg = f"🔬 ANALISTA → {emoji} (Confianza: {conf:.0f}% {conf_label})\n   📊 Señales: {signals_count} | Datos: {details['data_points']}"

            for sig_name, sig_data in details["signals"].items():
                pred_emoji = self._color_emoji(sig_data.get("prediction", "red"))
                if sig_name == "markov":
                    msg += f"\n   🔗 Markov: {pred_emoji} ({sig_data.get('confidence', 0)}%)"
                elif sig_name == "markov3":
                    msg += f"\n   🔗 Markov3: {pred_emoji} ({sig_data.get('confidence', 0)}%)"
                elif sig_name == "momentum":
                    msg += f"\n   🌊 Momentum: {pred_emoji} ({sig_data.get('signal', '')})"
                elif sig_name == "frequency":
                    msg += f"\n   📈 Frecuencia: {pred_emoji} (déficit {sig_data.get('deficit', 0):.1f}%)"
                elif sig_name == "alternation":
                    msg += f"\n   🔄 Alternancia: {pred_emoji} ({sig_data.get('pct', 0):.0f}%)"
                elif sig_name == "hot_cold":
                    msg += f"\n   🔥 Hot/Cold: {pred_emoji} ({sig_data.get('trend', '')})"

            self.on_prediction(msg)

    def get_full_report(self) -> str:
        data = self.archive.get_last_n(500)
        if len(data) < 10:
            return "📊 Sin datos suficientes para generar reporte."
        freq = self.analyzer.frequency_analysis(data, n=200)
        streaks = self.analyzer.streak_analysis(data, n=300)
        alt = self.analyzer.alternation_analysis(data, n=200)
        momentum = self.analyzer.momentum_analysis(data, n=100)
        hc = self.analyzer.hot_cold_analysis(data, window=15, n=200)
        accuracy = (self.predictions_correct / self.predictions_made * 100 if self.predictions_made > 0 else 0)

        report = (
            f"📊 REPORTE COMPLETO DE ANÁLISIS\n{'=' * 35}\n\n"
            f"📈 PRECISIÓN DEL ANALISTA:\n"
            f"  • Predicciones: {self.predictions_made}\n"
            f"  • Aciertos: {self.predictions_correct}\n"
            f"  • Precisión: {accuracy:.1f}%\n\n"
            f"📊 FRECUENCIA (últimos {freq.get('total', 0)}):\n"
            f"  • 🔴 Red: {freq.get('red', 0)} ({freq.get('red_pct', 0)}%)\n"
            f"  • 🔵 Blue: {freq.get('blue', 0)} ({freq.get('blue_pct', 0)}%)\n"
            f"  • Desviación: {freq.get('deviation', 0)}%\n"
            f"  • Z-Score: {freq.get('z_score', 0)}\n"
            f"  • Significativo: {'SÍ' if freq.get('significant') else 'NO'}\n\n"
            f"🔄 ALTERNANCIA:\n"
            f"  • Cambios: {alt.get('alternation_pct', 0)}%\n"
            f"  • Continuidad: {alt.get('continuity_pct', 0)}%\n"
            f"  • Tendencia: {alt.get('tends_to', 'N/A')}\n"
            f"  • Patrón 3 actual: {alt.get('last_pattern_3', 'N/A')}\n\n"
            f"🌊 MOMENTUM:\n"
            f"  • Tras rachas: {momentum.get('streak_signal', 'N/A')}\n"
            f"  • Continuación: {momentum.get('streak_continuation_pct', 0)}%\n"
            f"  • Reversión: {momentum.get('streak_reversal_pct', 0)}%\n\n"
            f"📏 RACHAS:\n"
            f"  • Promedio: {streaks.get('avg_length', 0)}\n"
            f"  • Máxima: {streaks.get('max_length', 0)}\n"
            f"  • Actual: {streaks.get('current_streak', {}).get('length', 'N/A')}\n\n"
            f"🔥 HOT/COLD (ventana 15):\n"
            f"  • 🔴 Hot: {hc.get('current_red', 0)}\n"
            f"  • 🔵 Cold: {hc.get('current_blue', 0)}\n"
            f"  • Tendencia: {hc.get('trend', 'N/A')}\n\n"
            f"💾 Total datos archivados: {self.archive.get_count()}"
        )
        return report

    def reset(self):
        self.last_prediction = None
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None
        self.predictions_made = 0
        self.predictions_correct = 0


# ==================== POLLING GLOBAL ====================
class GlobalPolling:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.user_predictors: Dict[int, object] = {}
        self.running = False
        self.last_processed_index = 0
        self.last_color_time = time.time()
        self.api_url = "https://www.ff2016.vip/api/game/getchart?lang=es"
        self.headers = {"Content-Type": "application/json"}
        self._lock = threading.Lock()
        self.reconnect_timeout = 90

    def register_user(self, user_id: int, mode: str, on_prediction=None, on_result=None, archive=None):
        with self._lock:
            if mode == "pro":
                predictor = ProPredictor(user_id)
            elif mode == "analista":
                if archive is None:
                    archive = ResultArchive()
                predictor = AnalystPredictor(user_id, archive)
            else:
                predictor = HackPredictor(user_id)
            predictor.on_prediction = on_prediction
            predictor.on_result = on_result
            self.user_predictors[user_id] = predictor
            return predictor

    def unregister_user(self, user_id: int):
        with self._lock:
            if user_id in self.user_predictors:
                self.user_predictors[user_id].active = False
                del self.user_predictors[user_id]

    def start(self):
        if self.running:
            return
        self.running = True
        threading.Thread(target=self._polling_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _polling_loop(self):
        while self.running:
            try:
                if time.time() - self.last_color_time > self.reconnect_timeout:
                    self.last_processed_index = 0
                    self.last_color_time = time.time()
                response = requests.post(self.api_url, headers=self.headers, timeout=10)
                if response.ok:
                    data = response.json()
                    if data.get('code') == 1:
                        all_colors = data['data']['ori']
                        if len(all_colors) > self.last_processed_index:
                            new_colors = all_colors[self.last_processed_index:]
                            self.last_processed_index = len(all_colors)
                            raw_color = str(new_colors[-1]).lower()
                            if raw_color in ['red', 'rojo', '🔴', '1', 'r']:
                                last_color = 'red'
                            elif raw_color in ['blue', 'azul', '🔵', '2', 'b']:
                                last_color = 'blue'
                            else:
                                try:
                                    last_color = 'red' if int(raw_color) == 1 else 'blue'
                                except:
                                    last_color = 'red'
                            self.last_color_time = time.time()
                            with self._lock:
                                for predictor in self.user_predictors.values():
                                    if predictor.active:
                                        predictor.process_color(last_color)
            except Exception as e:
                print(f"Error en polling: {e}")
            time.sleep(2)


# ==================== BOT DE TELEGRAM ====================
class PredictionBot:
    def __init__(self, token: str):
        self.token = token
        self.license_manager = LicenseManager()
        self.global_polling = GlobalPolling()
        self.result_archive = ResultArchive()
        self.user_sessions: Dict[int, Dict] = {}
        self.pending_payments: Dict[int, Dict] = {}
        self.application = None
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    async def _send_message(self, user_id: int, text: str):
        if self.application:
            try:
                await self.application.bot.send_message(chat_id=user_id, text=text)
            except Exception as e:
                print(f"Error enviando mensaje: {e}")

    def _sync_send_message(self, user_id: int, text: str):
        asyncio.run_coroutine_threadsafe(self._send_message(user_id, text), self.loop)

    async def _send_win_image(self, user_id: int):
        try:
            await self.application.bot.send_photo(chat_id=user_id, photo=WIN_IMAGE_URL, caption="✅ WIN")
        except:
            await self._send_message(user_id, "✅ WIN")

    def _sync_send_win_image(self, user_id: int):
        asyncio.run_coroutine_threadsafe(self._send_win_image(user_id), self.loop)

    async def _send_take_profit_image(self, user_id: int):
        try:
            await self.application.bot.send_photo(chat_id=user_id, photo=TAKE_PROFIT_IMAGE_URL, caption="🎯 TAKE PROFIT ALCANZADO")
        except:
            await self._send_message(user_id, "🎯 TAKE PROFIT ALCANZADO")

    def _sync_send_take_profit_image(self, user_id: int):
        asyncio.run_coroutine_threadsafe(self._send_take_profit_image(user_id), self.loop)

    # ==================== COMANDO /start ====================
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)

        if not license_check['valid']:
            keyboard = [
                [InlineKeyboardButton("🔧 Hack 30d - 15 USDT", callback_data='plan_hack')],
                [InlineKeyboardButton("🏆 PRO 90d - 60 USDT", callback_data='plan_pro')],
                [InlineKeyboardButton("🔬 Analista 90d - 100 USDT", callback_data='plan_analista')],
            ]
            await update.message.reply_text(
                "🔒 ACCESO RESTRINGIDO\n\nNo tienes licencia activa.\n\n"
                "💰 PLANES DISPONIBLES:\n"
                "• 🔧 Hack 30d: 15 USDT (1 cuenta) - Estrategia Anti-sistema\n"
                "• 🏆 PRO 90d: 60 USDT (1 cuenta) - BASE + ALTERNANCIA + DOBLE/TRIPLE\n"
                "• 🔬 Analista 90d: 100 USDT (1 cuenta) - Motor estadístico compuesto\n\n"
                "Selecciona una opción:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        license_data = license_check['data']
        plan_name = LICENSE_PLANS[license_data['plan']]['name']
        max_accounts = license_data.get('max_users', 1)
        mode = license_data.get('mode', 'hack')

        if mode == "hack":
            modo_texto = "⚡ HACK (Anti-sistema: seguir color + ANTI tras 2 pérdidas)"
        elif mode == "pro":
            modo_texto = "🏆 PRO (BASE + ALTERNANCIA + DOBLE/TRIPLE)"
        else:
            modo_texto = "🔬 ANALISTA (Motor estadístico: Markov + Momentum + Frecuencia + Alternancia + Hot/Cold)"

        keyboard = [
            [InlineKeyboardButton("📡 MODO SEÑALES", callback_data='signals_mode')],
            [InlineKeyboardButton("🤖 MODO AUTOMATICO", callback_data='auto_mode')],
            [InlineKeyboardButton("📜 Info Licencia", callback_data='license_info')],
            [InlineKeyboardButton("💰 Comprar Licencia", callback_data='buy_license')]
        ]

        await update.message.reply_text(
            f"🎰 PREDICTOR BOT V8\n\n"
            f"✅ Licencia: {plan_name}\n"
            f"🎲 Modo: {modo_texto}\n"
            f"👥 Máx cuentas: {max_accounts}\n\n"
            f"Selecciona una opción:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ==================== MODO SEÑALES ====================
    async def signals_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)

        if not license_check['valid']:
            await query.edit_message_text("❌ Licencia no válida. Usa /start")
            return

        mode = license_check['data'].get('mode', 'hack')

        if not self.global_polling.running:
            self.global_polling.start()

        def on_prediction(msg):
            self._sync_send_message(user_id, msg)

        def on_result(msg, is_win):
            self._sync_send_message(user_id, msg)
            if is_win:
                self._sync_send_win_image(user_id)

        if mode == "analista":
            self.global_polling.register_user(user_id, mode, on_prediction, on_result, archive=self.result_archive)
        else:
            self.global_polling.register_user(user_id, mode, on_prediction, on_result)

        self.user_sessions[user_id] = {'mode': 'signals', 'bot_mode': mode}

        if mode == "hack":
            desc = "• Sigue el último color que sale\n• Si falla 2 veces → MODO ANTI por 2 rondas"
        elif mode == "pro":
            desc = "• BASE + ALTERNANCIA + DOBLE/TRIPLE\n• TRIPLE siempre vuelve a BASE"
        else:
            desc = ("• Motor estadístico compuesto\n"
                    "• Cadenas de Markov (orden 2 y 3)\n"
                    "• Análisis de momentum y reversión\n"
                    "• Desviación de frecuencia\n"
                    "• Detección de alternancia\n"
                    "• Hot/Cold por ventana deslizante\n"
                    "• Necesita ~30 rondas para calibrar\n"
                    "• Usa /reporte para ver análisis completo")

        await query.edit_message_text(
            f"📡 MODO SEÑALES ACTIVADO - {mode.upper()}\n\n"
            f"🎯 Reglas:\n{desc}\n\n"
            f"Recibirás las señales automáticamente.\n"
            f"Usa /stop para detener.\n"
            f"Usa /reporte para ver estadísticas."
        )

    # ==================== MODO AUTOMATICO ====================
    async def auto_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)

        if not license_check['valid']:
            await query.edit_message_text("❌ No tienes licencia activa. Usa /start")
            return

        license_data = license_check['data']
        max_accounts = license_data.get('max_users', 1)
        mode = license_data.get('mode', 'hack')

        if mode == "hack":
            desc = "• Sigue el último color que sale\n• Si falla 2 veces → MODO ANTI por 2 rondas"
        elif mode == "pro":
            desc = "• BASE + ALTERNANCIA + DOBLE/TRIPLE\n• TRIPLE siempre vuelve a BASE"
        else:
            desc = ("• Motor estadístico compuesto\n"
                    "• Markov + Momentum + Frecuencia + Alternancia + Hot/Cold\n"
                    "• Necesita ~30 rondas para calibrar")

        await query.edit_message_text(
            f"🤖 MODO AUTOMATICO - {mode.upper()}\n\n"
            f"🎯 Reglas:\n{desc}\n\n"
            f"Envía tus credenciales:\n"
            f"usuario:contraseña\n\n"
            f"Máx {max_accounts} cuentas: user1:pass1,user2:pass2"
        )
        context.user_data['awaiting_credentials'] = True
        context.user_data['max_accounts'] = max_accounts
        context.user_data['mode'] = mode

    # ==================== PROCESAR CREDENCIALES ====================
    async def process_credentials(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        max_accounts = context.user_data.get('max_accounts', 1)
        mode = context.user_data.get('mode', 'hack')

        accounts_data = []
        if ',' in text:
            for part in text.split(','):
                if ':' in part.strip():
                    u, p = part.strip().split(':', 1)
                    accounts_data.append((u.strip(), p.strip()))
        elif ':' in text:
            u, p = text.split(':', 1)
            accounts_data.append((u.strip(), p.strip()))
        else:
            await update.message.reply_text("❌ Formato incorrecto. Usa usuario:contraseña")
            context.user_data['awaiting_credentials'] = False
            return

        if len(accounts_data) > max_accounts:
            await update.message.reply_text(f"❌ Máximo {max_accounts} cuentas")
            context.user_data['awaiting_credentials'] = False
            return

        await update.message.reply_text(f"🔄 Probando {len(accounts_data)} cuenta(s)...")

        accounts = []
        for username, password in accounts_data:
            acc = UserAccount(username, password)
            success, msg = acc.login()
            if success:
                accounts.append(acc)
                await update.message.reply_text(f"✅ {username}: ${acc.balance:.2f}")
            else:
                await update.message.reply_text(f"❌ {username}: {msg}")

        if accounts:
            await update.message.reply_text(f"✅ {len(accounts)} cuenta(s) conectada(s)")

            if not self.global_polling.running:
                self.global_polling.start()

            def on_prediction(msg):
                self._sync_send_message(user_id, msg)
                if self.user_sessions.get(user_id, {}).get('auto_betting_active'):
                    if '🔴' in msg:
                        self._execute_bets(user_id, 'red')
                    elif '🔵' in msg:
                        self._execute_bets(user_id, 'blue')

            def on_result(msg, is_win):
                self._sync_send_message(user_id, msg)
                if is_win:
                    self._sync_send_win_image(user_id)
                if self.user_sessions.get(user_id, {}).get('auto_betting_active'):
                    self._update_bet_on_result(user_id, is_win)
                    self._show_balances(user_id)

            if mode == "analista":
                self.global_polling.register_user(user_id, mode, on_prediction, on_result, archive=self.result_archive)
            else:
                self.global_polling.register_user(user_id, mode, on_prediction, on_result)

            self.user_sessions[user_id] = {
                'mode': 'auto', 'accounts': accounts,
                'auto_betting_active': False, 'bot_mode': mode,
                'bet_config': {
                    'initial_bet': 0.1, 'current_bet': 0.1, 'max_bet': 10.0,
                    'max_losses': 5, 'use_martingale': False, 'take_profit': 0.0,
                    'restart_bet': 0.1, 'max_pauses': 2,
                }
            }
            await self.show_betting_config(update, user_id)
        else:
            await update.message.reply_text("❌ No se pudo conectar ninguna cuenta")

        context.user_data['awaiting_credentials'] = False

    # ==================== EJECUTAR APUESTAS ====================
    def _execute_bets(self, user_id: int, color: str):
        session = self.user_sessions.get(user_id)
        if not session:
            return
        for account in session.get('accounts', []):
            if account.paused or not account.betting_active or account.balance <= 0:
                continue
            bet_amount = account.current_bet
            if bet_amount > account.balance:
                self._sync_send_message(user_id, f"❌ {account.username}: Saldo insuficiente para ${bet_amount:.2f}")
                continue
            success, msg = account.place_bet(color, bet_amount)
            if success:
                self._sync_send_message(user_id, f"💰 {account.username}: ${bet_amount:.2f} a {color.upper()}")
            else:
                self._sync_send_message(user_id, f"❌ {account.username}: {msg}")

    # ==================== ACTUALIZAR TRAS RESULTADO ====================
    def _update_bet_on_result(self, user_id: int, won: bool):
        session = self.user_sessions.get(user_id)
        if not session:
            return
        for account in session.get('accounts', []):
            if account.paused and won:
                account.reactivate_from_pause()
                self._sync_send_message(user_id, f"✅ WIN DETECTADO - ¡CUENTA REACTIVADA!")
                self._sync_send_message(user_id, f"🔄 Reiniciando apuestas a: ${account.restart_bet:.2f}")
                if account.saldo_perdido > 0:
                    self._sync_send_message(user_id, f"🎯 OBJETIVO: Recuperar ${account.saldo_perdido:.2f} perdidos")
                continue
            if not account.betting_active:
                continue
            if won:
                account.wins += 1
                account.reset_bet()
                if account.saldo_perdido > 0 and not account.saldo_recuperado:
                    if account.check_saldo_recuperado():
                        self._sync_send_message(user_id, f"🎉 ¡SALDO RECUPERADO! - {account.username}")
                        self._sync_send_message(user_id, f"💰 Ganancia recuperada: ${account.saldo_perdido:.2f}")
                        self._sync_send_message(user_id, f"🔄 Volviendo a apuesta inicial original: ${account.initial_bet_original:.2f}")
                        account.saldo_perdido = 0
                        account.saldo_inicial_pausa = 0
                self._sync_send_message(user_id, f"💰 {account.username}: WIN - Reiniciada a ${account.current_bet:.2f}")
                if account.check_take_profit():
                    account.betting_active = False
                    self._sync_send_message(user_id, f"🎯 ¡TAKE PROFIT ALCANZADO! {account.username}\n{account.get_profit_info()}\n🛑 Apuestas detenidas")
                    self._sync_send_take_profit_image(user_id)
            else:
                if account.paused:
                    continue
                account.losses += 1
                stop_loss_status = account.check_stop_loss()
                if stop_loss_status == "PAUSAR":
                    account.saldo_perdido = account.balance - account.saldo_inicial_pausa if account.saldo_inicial_pausa > 0 else 0
                    if account.activate_pause():
                        self._sync_send_message(user_id, f"🛑 STOP LOSS ALCANZADO - {account.username}")
                        self._sync_send_message(user_id, f"📉 Pérdidas consecutivas: {account.max_consecutive_losses}")
                        self._sync_send_message(user_id, f"💰 Saldo: ${account.balance:.2f} | Perdido: ${account.saldo_perdido:.2f}")
                        self._sync_send_message(user_id, f"💤 PAUSA #{account.current_pauses}/{account.max_pauses} - Esperando WIN para reiniciar")
                        account.betting_active = False
                elif stop_loss_status == "DETENER":
                    account.betting_active = False
                    self._sync_send_message(user_id, f"🛑 LÍMITE DE PAUSAS ALCANZADO - {account.username}")
                    self._sync_send_message(user_id, f"📊 Pausas: {account.current_pauses}/{account.max_pauses}")
                    self._sync_send_message(user_id, f"💤 DETENCIÓN PERMANENTE | Saldo: ${account.balance:.2f}")
                    self._sync_send_message(user_id, f"🔄 Usa /start para reiniciar manualmente")
                else:
                    msg = account.update_bet_on_loss()
                    self._sync_send_message(user_id, f"📉 {account.username}: {msg}")

    # ==================== MOSTRAR BALANCES ====================
    def _show_balances(self, user_id: int):
        session = self.user_sessions.get(user_id)
        if not session:
            return
        msg = "💰 SALDOS\n\n"
        for acc in session.get('accounts', []):
            acc.get_balance()
            msg += f"• {acc.username}: ${acc.balance:.2f}"
            if acc.paused:
                msg += f" ⏸️ (PAUSA {acc.current_pauses}/{acc.max_pauses})"
            if not acc.betting_active and not acc.paused:
                msg += f" ⛔ (DETENIDA)"
            msg += "\n"
            if acc.take_profit_amount > 0 and acc.initial_balance_snapshot > 0:
                profit = acc.balance - acc.initial_balance_snapshot
                msg += f"  📈 Meta: ${acc.take_profit_amount:.2f} | Ganancia: ${profit:.2f}\n"
            if acc.saldo_perdido > 0 and acc.paused:
                msg += f"  📉 Por recuperar: ${acc.saldo_perdido:.2f}\n"
        self._sync_send_message(user_id, msg)

    # ==================== CONFIGURACIÓN DE APUESTAS ====================
    async def show_betting_config(self, update, user_id):
        session = self.user_sessions[user_id]
        config = session['bet_config']
        bot_mode = session.get('bot_mode', 'hack')
        take_profit_val = config.get('take_profit', 0)
        tp_display = "DESACTIVADO" if take_profit_val == 0 else f"${take_profit_val}"

        if bot_mode == "hack":
            modo_texto = "HACK (Anti-sistema)"
        elif bot_mode == "pro":
            modo_texto = "PRO (BASE + ALTERNANCIA + DOBLE/TRIPLE)"
        else:
            modo_texto = "ANALISTA (Motor estadístico compuesto)"

        keyboard = [
            [InlineKeyboardButton(f"💰 Inicial: ${config['initial_bet']}", callback_data='cfg_initial')],
            [InlineKeyboardButton(f"📈 Máximo: ${config['max_bet']}", callback_data='cfg_max_bet')],
            [InlineKeyboardButton(f"🛑 Stop Loss: {config['max_losses']}", callback_data='cfg_max_losses')],
            [InlineKeyboardButton(f"🔄 Reinicio: ${config.get('restart_bet', 0.1)}", callback_data='cfg_restart_bet')],
            [InlineKeyboardButton(f"⏸️ Max Pausas: {config.get('max_pauses', 2)}", callback_data='cfg_max_pauses')],
            [InlineKeyboardButton(f"🎲 Modo: {'Martingala' if config['use_martingale'] else 'Agresivo'}", callback_data='cfg_mode')],
            [InlineKeyboardButton(f"🎯 Take Profit: {tp_display}", callback_data='cfg_take_profit')],
            [InlineKeyboardButton("📊 Ver Balances", callback_data='view_balances')],
            [InlineKeyboardButton("▶️ INICIAR AUTO-BET", callback_data='start_autobet')],
            [InlineKeyboardButton("◀️ Volver", callback_data='back_to_start')]
        ]

        msg = (
            f"⚙️ CONFIGURACIÓN - {modo_texto}\n\n"
            f"💰 Apuesta actual: ${config['current_bet']}\n"
            f"🎲 Modo gestión: {'Martingala (x2)' if config['use_martingale'] else 'Agresivo (x2+inicial)'}\n"
            f"🛑 Stop Loss: {config['max_losses']} pérdidas consecutivas\n"
            f"🔄 Reinicio: ${config.get('restart_bet', 0.1)}\n"
            f"⏸️ Max Pausas: {config.get('max_pauses', 2)}\n"
            f"🎯 Take Profit: {tp_display}\n\n"
            f"📌 Stop Loss → PAUSA → Espera WIN → Reinicia\n"
            f"📌 Recupera saldo perdido → Vuelve a apuesta original\n"
            f"📌 {config.get('max_pauses', 2)} pausas → DETENCIÓN PERMANENTE"
        )

        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    # ==================== HANDLERS DE CONFIGURACIÓN ====================
    async def cfg_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        current = self.user_sessions[user_id]['bet_config']['use_martingale']
        self.user_sessions[user_id]['bet_config']['use_martingale'] = not current
        for acc in self.user_sessions[user_id]['accounts']:
            acc.use_martingale = not current
        mode = "Martingala (x2)" if not current else "Agresivo (x2+inicial)"
        await update.callback_query.answer(f"Modo cambiado a {mode}")
        await self.show_betting_config(update, user_id)

    async def cfg_initial(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("💰 Envía nuevo monto inicial (mínimo 0.1):")
        context.user_data['awaiting_initial_bet'] = True

    async def cfg_restart_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("🔄 Envía el monto de REINICIO (mínimo 0.1):")
        context.user_data['awaiting_restart_bet'] = True

    async def cfg_max_pauses(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("⏸️ Envía el número máximo de pausas (1-5):")
        context.user_data['awaiting_max_pauses'] = True

    async def cfg_max_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("📈 Envía monto máximo:")
        context.user_data['awaiting_max_bet'] = True

    async def cfg_max_losses(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("🛑 Envía número máximo de pérdidas consecutivas (1-20):")
        context.user_data['awaiting_max_losses'] = True

    async def cfg_take_profit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "🎯 CONFIGURAR TAKE PROFIT\n\n"
            "Envía el monto de GANANCIA objetivo:\n"
            "• 5 → Detener cuando ganes $5\n"
            "• 10 → Detener cuando ganes $10\n"
            "• 0 → DESACTIVAR Take Profit"
        )
        context.user_data['awaiting_take_profit'] = True

    # ==================== PROCESAR VALORES DE CONFIG ====================
    async def process_initial_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            amount = float(update.message.text)
            if amount < 0.1:
                await update.message.reply_text("❌ Mínimo 0.1")
                return
            self.user_sessions[user_id]['bet_config']['initial_bet'] = amount
            self.user_sessions[user_id]['bet_config']['current_bet'] = amount
            if self.user_sessions[user_id]['bet_config'].get('restart_bet', 0) == 0:
                self.user_sessions[user_id]['bet_config']['restart_bet'] = amount
            for acc in self.user_sessions[user_id]['accounts']:
                acc.initial_bet = amount
                acc.initial_bet_original = amount
                acc.current_bet = amount
                if acc.restart_bet == 0:
                    acc.restart_bet = amount
            await update.message.reply_text(f"✅ Monto inicial: ${amount:.2f}")
            await self.show_betting_config(update, user_id)
        except:
            await update.message.reply_text("❌ Número inválido")
        context.user_data['awaiting_initial_bet'] = False

    async def process_restart_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            amount = float(update.message.text)
            if amount < 0.1:
                await update.message.reply_text("❌ Mínimo 0.1")
                return
            self.user_sessions[user_id]['bet_config']['restart_bet'] = amount
            for acc in self.user_sessions[user_id]['accounts']:
                acc.restart_bet = amount
            await update.message.reply_text(f"✅ Monto de reinicio: ${amount:.2f}")
            await self.show_betting_config(update, user_id)
        except:
            await update.message.reply_text("❌ Número inválido")
        context.user_data['awaiting_restart_bet'] = False

    async def process_max_pauses(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            value = int(update.message.text)
            if value < 1 or value > 5:
                await update.message.reply_text("❌ Valor entre 1 y 5")
                return
            self.user_sessions[user_id]['bet_config']['max_pauses'] = value
            for acc in self.user_sessions[user_id]['accounts']:
                acc.max_pauses = value
            await update.message.reply_text(f"✅ Máximo de pausas: {value}")
            await self.show_betting_config(update, user_id)
        except:
            await update.message.reply_text("❌ Número inválido")
        context.user_data['awaiting_max_pauses'] = False

    async def process_max_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            amount = float(update.message.text)
            if amount < 0.1:
                await update.message.reply_text("❌ Mínimo 0.1")
                return
            self.user_sessions[user_id]['bet_config']['max_bet'] = amount
            for acc in self.user_sessions[user_id]['accounts']:
                acc.max_bet = amount
            await update.message.reply_text(f"✅ Máximo: ${amount:.2f}")
            await self.show_betting_config(update, user_id)
        except:
            await update.message.reply_text("❌ Número inválido")
        context.user_data['awaiting_max_bet'] = False

    async def process_max_losses(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            value = int(update.message.text)
            if value < 1 or value > 20:
                await update.message.reply_text("❌ Valor entre 1 y 20")
                return
            self.user_sessions[user_id]['bet_config']['max_losses'] = value
            for acc in self.user_sessions[user_id]['accounts']:
                acc.max_consecutive_losses = value
            await update.message.reply_text(f"✅ Stop Loss: {value} pérdidas consecutivas")
            await self.show_betting_config(update, user_id)
        except:
            await update.message.reply_text("❌ Número inválido")
        context.user_data['awaiting_max_losses'] = False

    async def process_take_profit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            amount = float(update.message.text)
            if amount < 0:
                await update.message.reply_text("❌ No puede ser negativo")
                return
            self.user_sessions[user_id]['bet_config']['take_profit'] = amount
            if amount == 0:
                await update.message.reply_text("✅ Take Profit DESACTIVADO")
            else:
                await update.message.reply_text(f"✅ Take Profit: ${amount:.2f}")
            await self.show_betting_config(update, user_id)
        except:
            await update.message.reply_text("❌ Número inválido")
        context.user_data['awaiting_take_profit'] = False

    # ==================== INICIAR AUTO-BET ====================
    async def start_autobet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await update.callback_query.answer("❌ No hay cuentas")
            return

        config = self.user_sessions[user_id]['bet_config']
        bot_mode = self.user_sessions[user_id].get('bot_mode', 'hack')
        take_profit_amount = config.get('take_profit', 0)
        restart_bet = config.get('restart_bet', 0.1)
        max_pauses = config.get('max_pauses', 2)

        for acc in self.user_sessions[user_id]['accounts']:
            acc.initial_bet = config['initial_bet']
            acc.initial_bet_original = config['initial_bet']
            acc.current_bet = config['initial_bet']
            acc.max_bet = config['max_bet']
            acc.max_consecutive_losses = config['max_losses']
            acc.use_martingale = config['use_martingale']
            acc.consecutive_losses = 0
            acc.betting_active = True
            acc.restart_bet = restart_bet
            acc.max_pauses = max_pauses
            acc.current_pauses = 0
            acc.paused = False
            acc.waiting_for_win = False
            acc.saldo_inicial_pausa = 0.0
            acc.saldo_perdido = 0.0
            acc.saldo_recuperado = False
            acc.get_balance()
            acc.initial_balance_snapshot = acc.balance
            acc.take_profit_amount = take_profit_amount

        self.user_sessions[user_id]['auto_betting_active'] = True

        modo_texto = "Martingala (x2)" if config['use_martingale'] else "Agresivo (x2+inicial)"
        tp_texto = f"${take_profit_amount}" if take_profit_amount > 0 else "DESACTIVADO"

        if bot_mode == "hack":
            reglas = "• Sigue el último color\n• Si falla 2x → MODO ANTI por 2 rondas"
        elif bot_mode == "pro":
            reglas = "• BASE + ALTERNANCIA + DOBLE/TRIPLE\n• TRIPLE siempre vuelve a BASE"
        else:
            reglas = "• Motor estadístico compuesto\n• Markov + Momentum + Frecuencia + Alternancia + Hot/Cold"

        await update.callback_query.edit_message_text(
            f"✅ AUTO-BET ACTIVADO - {bot_mode.upper()}\n\n"
            f"🎯 Reglas:\n{reglas}\n\n"
            f"💰 Inicial: ${config['initial_bet']}\n"
            f"📈 Máximo: ${config['max_bet']}\n"
            f"🛑 Stop Loss: {config['max_losses']} pérdidas\n"
            f"🔄 Reinicio: ${restart_bet}\n"
            f"⏸️ Max Pausas: {max_pauses}\n"
            f"🎲 Gestión: {modo_texto}\n"
            f"🎯 Take Profit: {tp_texto}\n"
            f"📊 Cuentas: {len(self.user_sessions[user_id]['accounts'])}\n\n"
            f"Usa /stop para detener."
        )

    # ==================== VER BALANCES ====================
    async def view_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        session = self.user_sessions.get(user_id)
        if not session:
            await update.callback_query.answer("No hay sesión")
            return
        msg = "💰 BALANCES\n\n"
        for acc in session.get('accounts', []):
            acc.get_balance()
            msg += f"• {acc.username}: ${acc.balance:.2f}"
            if acc.paused:
                msg += f" ⏸️ (PAUSA {acc.current_pauses}/{acc.max_pauses})"
            if not acc.betting_active and not acc.paused:
                msg += f" ⛔ (DETENIDA)"
            msg += "\n"
            if acc.take_profit_amount > 0 and acc.initial_balance_snapshot > 0:
                profit = acc.balance - acc.initial_balance_snapshot
                msg += f"  📈 Meta: ${acc.take_profit_amount:.2f} | Ganancia: ${profit:.2f}\n"
            if acc.saldo_perdido > 0 and acc.paused:
                msg += f"  📉 Por recuperar: ${acc.saldo_perdido:.2f}\n"
            if acc.saldo_recuperado:
                msg += f"  ✅ Saldo recuperado\n"
        await update.callback_query.edit_message_text(msg)

    # ==================== COMPRAR LICENCIA ====================
    async def buy_license(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔧 Hack 30d - 15 USDT", callback_data='plan_hack')],
            [InlineKeyboardButton("🏆 PRO 90d - 60 USDT", callback_data='plan_pro')],
            [InlineKeyboardButton("🔬 Analista 90d - 100 USDT", callback_data='plan_analista')],
        ]
        await update.callback_query.edit_message_text(
            "💰 COMPRAR LICENCIA\n\nSelecciona un plan:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def select_plan(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        plan_id = query.data.replace('plan_', '')
        user_id = update.effective_user.id
        plan = LICENSE_PLANS.get(plan_id)
        if not plan:
            await query.edit_message_text("❌ Plan inválido")
            return

        self.pending_payments[user_id] = {
            'plan': plan_id, 'amount': plan['price'],
            'username': update.effective_user.username or update.effective_user.first_name,
            'user_id': user_id
        }

        keyboard = [
            [InlineKeyboardButton("📸 Enviar Comprobante", callback_data='send_payment_proof')],
            [InlineKeyboardButton("◀️ Volver", callback_data='back_to_start')]
        ]

        await query.edit_message_text(
            f"💸 PAGO REQUERIDO\n\n"
            f"📦 Plan: {plan['name']}\n"
            f"💰 Monto: {plan['price']} USDT (BEP20)\n\n"
            f"📤 Wallet:\n`{MY_WALLET_BEP20}`\n\n"
            f"1️⃣ Transferir {plan['price']} USDT\n"
            f"2️⃣ Toca 📸 Enviar Comprobante\n"
            f"3️⃣ Adjunta CAPTURA con TXID\n\n"
            f"🆔 Tu ID: `{user_id}`",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )

    async def send_payment_proof(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        if user_id not in self.pending_payments:
            await query.edit_message_text("❌ No hay compra pendiente")
            return
        plan_name = LICENSE_PLANS[self.pending_payments[user_id]['plan']]['name']
        await query.edit_message_text(
            f"📸 ENVIA CAPTURA\n\n"
            f"📦 Plan: {plan_name}\n"
            f"💰 Monto: {self.pending_payments[user_id]['amount']} USDT\n\n"
            f"Adjunta la imagen con el TXID visible"
        )
        context.user_data['awaiting_payment_proof'] = True

    async def handle_payment_proof(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if not context.user_data.get('awaiting_payment_proof') or user_id not in self.pending_payments:
            await update.message.reply_text("❌ No hay compra pendiente")
            context.user_data['awaiting_payment_proof'] = False
            return

        plan_info = self.pending_payments[user_id]
        plan_name = LICENSE_PLANS[plan_info['plan']]['name']
        amount = plan_info['amount']
        username = update.effective_user.username or update.effective_user.first_name

        txid = "No especificado"
        if update.message.caption:
            match = re.search(r'(0x[a-fA-F0-9]{64})', update.message.caption)
            if match:
                txid = match.group(0)

        admin_msg = (
            f"🆕 NUEVO PAGO\n\n"
            f"👤 @{username}\n🆔 {user_id}\n"
            f"📦 {plan_name}\n💰 {amount} USDT\n"
            f"📝 TXID: {txid}\n\n"
            f"✅ /validar {user_id} {plan_info['plan']}"
        )

        try:
            if update.message.photo:
                photo = update.message.photo[-1]
                await self.application.bot.send_photo(
                    chat_id=ADMIN_GROUP_ID, photo=photo.file_id, caption=admin_msg
                )
                await update.message.reply_text("✅ Comprobante enviado. En breve será verificado")
                del self.pending_payments[user_id]
            else:
                await update.message.reply_text("❌ Envía una imagen con el comprobante")
                return
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:100]}")
        context.user_data['awaiting_payment_proof'] = False

    async def license_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)

        if license_check['valid']:
            data = license_check['data']
            expiry = datetime.fromisoformat(data['expiry'])
            days = (expiry - datetime.now()).days
            mode = data.get('mode', 'hack')
            if mode == "hack":
                desc = "HACK: Sigue color + ANTI tras 2 pérdidas"
            elif mode == "pro":
                desc = "PRO: BASE + ALTERNANCIA + DOBLE/TRIPLE"
            else:
                desc = "ANALISTA: Markov + Momentum + Frecuencia + Alternancia + Hot/Cold"
            await query.edit_message_text(
                f"📜 LICENCIA\n\n"
                f"📋 Plan: {LICENSE_PLANS[data['plan']]['name']}\n"
                f"🎲 Estrategia: {desc}\n"
                f"🔢 Máx cuentas: {data.get('max_users', 1)}\n"
                f"📅 Activada: {datetime.fromisoformat(data['activated']).strftime('%Y-%m-%d')}\n"
                f"⏰ Expira: {expiry.strftime('%Y-%m-%d')}\n"
                f"📆 Días restantes: {days}"
            )
        else:
            await query.edit_message_text("❌ Sin licencia activa. Usa /start")

    # ==================== COMANDO /reporte ====================
    async def report_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await update.message.reply_text("❌ No hay sesión activa. Usa /start")
            return
        predictor = self.global_polling.user_predictors.get(user_id)
        if isinstance(predictor, AnalystPredictor):
            report = predictor.get_full_report()
            if len(report) > 4000:
                parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
                for part in parts:
                    await update.message.reply_text(part)
            else:
                await update.message.reply_text(report)
        else:
            await update.message.reply_text("❌ /reporte solo disponible en modo ANALISTA.\n\nEn modo HACK o PRO usa /start para ver tu estrategia.")

    # ==================== COMANDO /archivo (admin) ====================
    async def archive_stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        total = self.result_archive.get_count()
        last_100 = self.result_archive.get_last_n(100)
        analyzer = PatternAnalyzer(self.result_archive)
        freq = analyzer.frequency_analysis(last_100, n=100)
        streaks = analyzer.streak_analysis(last_100, n=100)
        msg = (
            f"🗄️ ESTADO DEL ARCHIVO\n\n"
            f"💾 Total resultados: {total}\n"
            f"📊 Últimos 100:\n"
            f"  • 🔴 Red: {freq.get('red', 0)} ({freq.get('red_pct', 0)}%)\n"
            f"  • 🔵 Blue: {freq.get('blue', 0)} ({freq.get('blue_pct', 0)}%)\n"
            f"  • Rachas promedio: {streaks.get('avg_length', 0)}\n"
            f"  • Racha máxima: {streaks.get('max_length', 0)}\n"
        )
        await update.message.reply_text(msg)

    # ==================== COMANDO /limpiar (admin) ====================
    async def clear_archive_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ No autorizado")
            return
        self.result_archive.clear_all()
        await update.message.reply_text("✅ Archivo de resultados limpiado")

    # ==================== OTROS COMANDOS ====================
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.user_sessions:
            self.user_sessions[user_id]['auto_betting_active'] = False
            self.global_polling.unregister_user(user_id)
            del self.user_sessions[user_id]
        await update.message.reply_text("⏹️ Bot detenido. Usa /start para volver.")

    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("❌ Operación cancelada")

    async def validate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ No autorizado")
            return
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "📋 USO: /validar USER_ID PLAN\n\n"
                "PLANES:\n• hack - 15 USDT (30d)\n• pro - 60 USDT (90d)\n• analista - 100 USDT (90d)\n\n"
                "Ejemplo: /validar 123456789 hack"
            )
            return
        try:
            target_user_id = int(args[0])
            plan = args[1]
            if plan not in LICENSE_PLANS:
                await update.message.reply_text(f"❌ Plan '{plan}' no válido. Usa: hack, pro, analista")
                return
            if self.license_manager.activate_license(target_user_id, plan):
                plan_name = LICENSE_PLANS[plan]['name']
                await update.message.reply_text(f"✅ Licencia '{plan_name}' activada para {target_user_id}")
                if plan == "hack":
                    mode_desc = "HACK (Anti-sistema)"
                elif plan == "pro":
                    mode_desc = "PRO (BASE + ALTERNANCIA + DOBLE/TRIPLE)"
                else:
                    mode_desc = "ANALISTA (Markov + Momentum + Frecuencia + Alternancia + Hot/Cold)"
                await self._send_message(
                    target_user_id,
                    f"🎉 ¡LICENCIA ACTIVADA!\n\n"
                    f"📦 Plan: {plan_name}\n"
                    f"🎲 Estrategia: {mode_desc}\n\n"
                    f"Usa /start para comenzar."
                )
            else:
                await update.message.reply_text("❌ Error al activar")
        except ValueError:
            await update.message.reply_text("❌ USER_ID debe ser un número")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)}")

    async def back_to_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.start_command(update, context)

    async def handle_any_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.pending_payments:
            await self.handle_payment_proof(update, context)
        else:
            await update.message.reply_text("📸 No hay compra pendiente.\nUsa /start para comprar licencia.")

    async def handle_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get('awaiting_credentials'):
            await self.process_credentials(update, context)
        elif context.user_data.get('awaiting_initial_bet'):
            await self.process_initial_bet(update, context)
        elif context.user_data.get('awaiting_restart_bet'):
            await self.process_restart_bet(update, context)
        elif context.user_data.get('awaiting_max_pauses'):
            await self.process_max_pauses(update, context)
        elif context.user_data.get('awaiting_max_bet'):
            await self.process_max_bet(update, context)
        elif context.user_data.get('awaiting_max_losses'):
            await self.process_max_losses(update, context)
        elif context.user_data.get('awaiting_take_profit'):
            await self.process_take_profit(update, context)
        elif context.user_data.get('awaiting_payment_proof'):
            if update.message.photo:
                await self.handle_payment_proof(update, context)
            else:
                await update.message.reply_text("❌ Envía una imagen con el comprobante")
        else:
            await update.message.reply_text("❌ Comando no reconocido.\nUsa /start para ver opciones.")

    # ==================== RUN ====================
    def run(self):
        self.application = Application.builder().token(self.token).build()

        # Comandos
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel_command))
        self.application.add_handler(CommandHandler("validar", self.validate_command))
        self.application.add_handler(CommandHandler("reporte", self.report_command))
        self.application.add_handler(CommandHandler("archivo", self.archive_stats_command))
        self.application.add_handler(CommandHandler("limpiar", self.clear_archive_command))

        # Callbacks
        self.application.add_handler(CallbackQueryHandler(self.signals_mode, pattern='signals_mode'))
        self.application.add_handler(CallbackQueryHandler(self.auto_mode, pattern='auto_mode'))
        self.application.add_handler(CallbackQueryHandler(self.buy_license, pattern='buy_license'))
        self.application.add_handler(CallbackQueryHandler(self.select_plan, pattern='plan_'))
        self.application.add_handler(CallbackQueryHandler(self.send_payment_proof, pattern='send_payment_proof'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_initial, pattern='cfg_initial'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_restart_bet, pattern='cfg_restart_bet'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_max_pauses, pattern='cfg_max_pauses'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_max_bet, pattern='cfg_max_bet'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_max_losses, pattern='cfg_max_losses'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_take_profit, pattern='cfg_take_profit'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_mode, pattern='cfg_mode'))
        self.application.add_handler(CallbackQueryHandler(self.start_autobet, pattern='start_autobet'))
        self.application.add_handler(CallbackQueryHandler(self.view_balances, pattern='view_balances'))
        self.application.add_handler(CallbackQueryHandler(self.license_info, pattern='license_info'))
        self.application.add_handler(CallbackQueryHandler(self.back_to_start, pattern='back_to_start'))

        # Mensajes
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_messages))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_any_photo))

        print("=" * 70)
        print("🎰 PREDICTOR BOT V8 COMPLETO")
        print("=" * 70)
        print("💰 PLANES:")
        print("  • 🔧 Hack 30d: 15 USDT - Anti-sistema")
        print("  • 🏆 PRO 90d: 60 USDT - BASE + ALTERNANCIA + DOBLE/TRIPLE")
        print("  • 🔬 Analista 90d: 100 USDT - Motor estadístico compuesto")
        print("=" * 70)
        print("🔬 ANALISTA - Señales:")
        print("  • Cadenas de Markov (orden 2 y 3)")
        print("  • Análisis de momentum/reversión")
        print("  • Desviación de frecuencia (Z-Score)")
        print("  • Detección de alternancia")
        print("  • Hot/Cold por ventana deslizante")
        print("  • Archivo SQLite persistente")
        print("=" * 70)
        print("📋 COMANDOS:")
        print("  /start - Menú principal")
        print("  /stop - Detener bot")
        print("  /reporte - Ver análisis completo (Analista)")
        print("  /archivo - Estado del archivo de datos")
        print("  /limpiar - Limpiar archivo (admin)")
        print("  /validar USER PLAN - Activar licencia (admin)")
        print("=" * 70)
        print("✅ BOT LISTO")
        print("=" * 70)

        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    print("🚀 INICIANDO PREDICTOR BOT V8 COMPLETO (HACK + PRO + ANALISTA)...")
    bot = PredictionBot(BOT_TOKEN)
    bot.run()