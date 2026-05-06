# bot.py - PREDICTOR PRO BOT (4 MODOS + HACK SIMPLIFICADO)
# VERSIÓN DEFINITIVA - HACK: MISMO COLOR + ALTERNANCIA 3

import json
import os
import threading
import time
import requests
import asyncio
import re
from collections import deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== CONFIGURACIÓN ====================
BOT_TOKEN = "8594158160:AAHA62kshI4eefINOsqh65wHdEtjCv61ed8"
ADMIN_IDS = [5541162744]
ADMIN_GROUP_ID = -1002513713257
MY_WALLET_BEP20 = "0x621917958C7ac81190e9f876C23D6B9914f31263"

# IMAGEN DE WIN
WIN_IMAGE_URL = "https://i.postimg.cc/T2pH8v1q/1777831023149.png"

# ==================== PLANES DE LICENCIA ====================
LICENSE_PLANS = {
    "standard": {"price": 10, "days": 30, "mode": "standard", "max_users": 1, "name": "📅 Estándar Mejorado 30 Días"},
    "peakbreak": {"price": 15, "days": 30, "mode": "peakbreak", "max_users": 1, "name": "📊 Peak-Break 30 Días"},
    "peakhack": {"price": 18, "days": 30, "mode": "peakhack", "max_users": 1, "name": "🔧 Peak Hack Alternancia 30 Días"},
    "ghost": {"price": 20, "days": 30, "mode": "ghost", "max_users": 1, "name": "👻 Peak-Ghost 30 Días"},
    "multiuser": {"price": 45, "days": 30, "mode": "flexible", "max_users": 5, "name": "👥 Multiuser 30 Días"},
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
            "user_id": user_id, "plan": plan, "activated": datetime.now().isoformat(),
            "expiry": expiry_date.isoformat(), "mode": plan_config["mode"],
            "max_users": plan_config["max_users"], "active": True
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
        days = (expiry - datetime.now()).days
        return max(0, days)

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
        self.current_bet = 0.1
        self.max_consecutive_losses = 5
        self.max_bet = 10.0
        self.consecutive_losses = 0
        self.wins = 0
        self.losses = 0
        self.betting_active = True
        self.use_martingale = False
        
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
            return f"Agressive (x2+inicial): ${new_bet:.2f}"

# ==================== CLASE BASE CON NORMALIZACIÓN ====================
class BaseStrategy:
    @staticmethod
    def normalizar_color(color: str) -> str:
        """Convierte cualquier color a 'red' o 'blue'"""
        if color is None:
            return 'red'
        
        c = str(color).lower().strip()
        
        if c in ['red', 'rojo', '🔴', '1', 'r']:
            return 'red'
        if c in ['blue', 'azul', '🔵', '2', 'b']:
            return 'blue'
        
        # Mapear emojis que puedan llegar
        if '🟢' in c or '⚪' in c:
            return 'red'
        if '🟡' in c:
            return 'blue'
        
        return 'red'

# ==================== ESTRATEGIA 1: ESTÁNDAR MEJORADO ====================
class StandardStrategy(BaseStrategy):
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.history_window = deque(maxlen=20)
        self.pending_bet = None
        self.rounds_to_wait = 0
        self.active = True
        self.total_wins = 0
        self.total_losses = 0
        self.on_status = None
        self.on_prediction = None
        self.on_result = None
    
    def _get_minority_color(self):
        if len(self.history_window) < 5:
            return None
        last_5 = list(self.history_window)[-5:]
        red_count = last_5.count('red')
        blue_count = last_5.count('blue')
        if red_count < blue_count:
            return 'red'
        elif blue_count < red_count:
            return 'blue'
        return None
    
    def _get_historial_str(self):
        last_10 = list(self.history_window)[-10:] if len(self.history_window) >= 10 else list(self.history_window)
        return ''.join(['🔴' if c == 'red' else '🔵' for c in last_10])
    
    def _update_status_display(self, current_color: str):
        color_emoji = "🔴" if current_color == 'red' else "🔵"
        historial = self._get_historial_str()
        if self.rounds_to_wait > 0:
            estado = f"⏳ Esperando {self.rounds_to_wait} ronda(s)"
        elif len(self.history_window) < 5:
            estado = f"📊 Recopilando datos ({len(self.history_window)}/5)..."
        else:
            estado = "📊 Analizando minoría..."
        if self.on_status:
            self.on_status(f"{color_emoji}\nHistorial: {historial}\n{estado}")
    
    def _make_prediction(self):
        if self.rounds_to_wait > 0 or len(self.history_window) < 5:
            return
        prediction = self._get_minority_color()
        if prediction:
            self.pending_bet = prediction
            pred_emoji = "🔴" if prediction == 'red' else "🔵"
            if self.on_prediction:
                self.on_prediction(f"🎯 ESTÁNDAR: {pred_emoji}")
    
    def process_color(self, color: str):
        if not self.active:
            return
        color = self.normalizar_color(color)
        if self.pending_bet is not None:
            is_win = (self.pending_bet == color)
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN", True)
                    self.total_wins += 1
                else:
                    self.on_result(f"❌ LOSS - Esperando 1 ronda", False)
                    self.total_losses += 1
            if is_win:
                self.rounds_to_wait = 0
            else:
                self.rounds_to_wait = 1
            self.pending_bet = None
            self.history_window.append(color)
            self._update_status_display(color)
            if is_win:
                self._make_prediction()
            return
        self.history_window.append(color)
        self._update_status_display(color)
        if self.rounds_to_wait > 0:
            self.rounds_to_wait -= 1
            return
        if len(self.history_window) >= 5:
            self._make_prediction()
    
    def reset(self):
        self.history_window.clear()
        self.pending_bet = None
        self.rounds_to_wait = 0
        self.total_wins = 0
        self.total_losses = 0

# ==================== ESTRATEGIA 2: PEAK-BREAK ====================
class PeakBreakStrategy(StandardStrategy):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.peak_active = False
        self.loss_streak = 0
    
    def _update_status_display(self, current_color: str):
        color_emoji = "🔴" if current_color == 'red' else "🔵"
        historial = self._get_historial_str()
        if self.peak_active:
            estado = "⚡ ACTIVO (apostando opuesto)"
        else:
            remaining = 2 - self.loss_streak
            estado = f"⏳ Peak-Break: esperando {remaining} LOSS para activar"
        if self.on_status:
            self.on_status(f"{color_emoji}\nHistorial: {historial}\n{estado}")
    
    def _make_prediction(self):
        if self.rounds_to_wait > 0 or len(self.history_window) == 0:
            return
        current_color = list(self.history_window)[-1]
        prediction = 'blue' if current_color == 'red' else 'red'
        self.pending_bet = prediction
        pred_emoji = "🔴" if prediction == 'red' else "🔵"
        if self.on_prediction:
            self.on_prediction(f"🎯 PEAK-BREAK: {pred_emoji}")
    
    def process_color(self, color: str):
        if not self.active:
            return
        color = self.normalizar_color(color)
        if self.peak_active and self.pending_bet is not None:
            is_win = (self.pending_bet == color)
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN", True)
                    self.total_wins += 1
                else:
                    self.on_result(f"❌ LOSS", False)
                    self.total_losses += 1
            if is_win:
                self.peak_active = False
                self.loss_streak = 0
            self.pending_bet = None
            self.history_window.append(color)
            self._update_status_display(color)
            return
        self.history_window.append(color)
        if len(self.history_window) >= 2:
            last_two = list(self.history_window)[-2:]
            self.loss_streak = 2 if last_two[0] == last_two[1] else 1
        else:
            self.loss_streak = 1
        if not self.peak_active and self.loss_streak >= 2:
            self.peak_active = True
            if self.on_status:
                self.on_status("⚡ PEAK-BREAK ACTIVADO")
        self._update_status_display(color)
        if self.peak_active and self.pending_bet is None:
            self._make_prediction()

# ==================== ESTRATEGIA 3: HACK SIMPLIFICADO ====================
class HackAlternancia3Strategy(StandardStrategy):
    """
    ESTRATEGIA HACK DEFINITIVA:
    - BASE: apostar al MISMO color
    - Alternancia (🔴🔵🔴 o 🔵🔴🔵): activar modo y apostar OPUESTO
    - SIN PATRONES, SIN DOBLE, SIN TRIPLE, SIN PAUSAS
    """
    
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.modo_alternancia = False
    
    def _ultimos_3_son_alternancia(self) -> bool:
        if len(self.history_window) < 3:
            return False
        ultimos_3 = list(self.history_window)[-3:]
        return ultimos_3[0] != ultimos_3[1] and ultimos_3[1] != ultimos_3[2]
    
    def _get_historial_str(self):
        last_10 = list(self.history_window)[-10:] if len(self.history_window) >= 10 else list(self.history_window)
        return ''.join(['🔴' if c == 'red' else '🔵' for c in last_10])
    
    def _update_status_display(self, current_color: str):
        color_emoji = "🔴" if current_color == 'red' else "🔵"
        color_text = "ROJO" if current_color == 'red' else "AZUL"
        historial = self._get_historial_str()
        
        if self.modo_alternancia:
            estado = "🔄 MODO ALTERNANCIA (apostando al OPUESTO)"
        else:
            estado = "🔵 MODO BASE (apostando al MISMO)"
        
        if self.on_status:
            self.on_status(f"{color_emoji} {color_text}\n📜 Historial: {historial}\n{estado}")
    
    def _make_prediction(self):
        if len(self.history_window) == 0:
            return
        
        ultimo = list(self.history_window)[-1]
        
        # Modo ALTERNANCIA activo
        if self.modo_alternancia:
            self.pending_bet = 'blue' if ultimo == 'red' else 'red'
            if self.on_prediction:
                pred_emoji = "🔴" if self.pending_bet == 'red' else "🔵"
                self.on_prediction(f"🎯 SEÑAL HACK: {pred_emoji}")
            return
        
        # Alternancia detectada (activar modo)
        if self._ultimos_3_son_alternancia():
            self.modo_alternancia = True
            self.pending_bet = 'blue' if ultimo == 'red' else 'red'
            if self.on_prediction:
                pred_emoji = "🔴" if self.pending_bet == 'red' else "🔵"
                self.on_prediction(f"🎯 SEÑAL HACK: {pred_emoji}")
            return
        
        # Modo BASE
        self.pending_bet = ultimo
        pred_emoji = "🔴" if self.pending_bet == 'red' else "🔵"
        if self.on_prediction:
            self.on_prediction(f"🎯 SEÑAL HACK: {pred_emoji}")
    
    def process_color(self, color: str):
        if not self.active:
            return
        
        color = self.normalizar_color(color)
        
        # Resolver apuesta pendiente
        if self.pending_bet is not None:
            is_win = (self.pending_bet == color)
            
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN", True)
                    self.total_wins += 1
                else:
                    self.on_result(f"❌ LOSS", False)
                    self.total_losses += 1
                    
                    # Perder en alternancia → se rompe
                    if self.modo_alternancia:
                        self.modo_alternancia = False
                        if self.on_status:
                            self.on_status("🔴 Alternancia rota - Volviendo a modo BASE")
            
            self.pending_bet = None
            self.history_window.append(color)
            self._update_status_display(color)
            self._make_prediction()
            return
        
        # Agregar color al historial
        self.history_window.append(color)
        self._update_status_display(color)
        
        # Generar nueva predicción
        self._make_prediction()
    
    def reset(self):
        super().reset()
        self.modo_alternancia = False

# ==================== ESTRATEGIA 4: PEAK-GHOST ====================
class PeakGhostStrategy(StandardStrategy):
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.waiting_for_win = False
        self.waiting_for_losses = False
        self.loss_count = 0
    
    def _get_last_5_colors(self):
        if len(self.history_window) < 5:
            return list(self.history_window)
        return list(self.history_window)[-5:]
    
    def _detect_pattern(self):
        last_5 = self._get_last_5_colors()
        if len(last_5) < 5:
            return ('nada', None, None)
        for i in range(len(last_5) - 2):
            if last_5[i] == last_5[i+1] == last_5[i+2]:
                color = last_5[i]
                expected = 'blue' if color == 'red' else 'red'
                return ('triple', color, expected)
        for i in range(len(last_5) - 1):
            if last_5[i] == last_5[i+1]:
                color = last_5[i]
                expected = 'blue' if color == 'red' else 'red'
                return ('doble', color, expected)
        es_alternancia = all(last_5[i] != last_5[i+1] for i in range(4))
        if es_alternancia:
            expected = 'blue' if last_5[-1] == 'red' else 'red'
            return ('alternancia', last_5[-1], expected)
        return ('nada', None, None)
    
    def _check_pattern_match(self, ghost_signal: str) -> bool:
        patron, color, expected = self._detect_pattern()
        if patron == 'nada':
            if self.on_status:
                self.on_status(f"🔍 Sin patrón claro")
            return False
        expected_emoji = "🔴" if expected == 'red' else "🔵"
        ghost_emoji = "🔴" if ghost_signal == 'red' else "🔵"
        if self.on_status:
            self.on_status(f"🔍 Patrón {patron} detectado - espera {expected_emoji}")
        if ghost_signal == expected:
            if self.on_status:
                self.on_status(f"✅ Señal GHOST {ghost_emoji} COINCIDE → APOSTAR")
            return True
        else:
            if self.on_status:
                self.on_status(f"❌ Señal GHOST {ghost_emoji} NO coincide → PASAR")
            return False
    
    def _update_status_display(self, current_color: str):
        color_emoji = "🔴" if current_color == 'red' else "🔵"
        historial = self._get_historial_str()
        if self.waiting_for_win:
            estado = "👻 ESPERANDO WIN..."
        elif self.waiting_for_losses:
            estado = f"👻 Buscando 1 LOSS (lleva {self.loss_count})"
        else:
            estado = "📊 APOSTANDO"
        if self.on_status:
            self.on_status(f"{color_emoji}\nHistorial: {historial}\n{estado}")
    
    def _execute_ghost_bet(self):
        if len(self.history_window) == 0:
            return
        ghost_signal = list(self.history_window)[-1]
        if not self._check_pattern_match(ghost_signal):
            self.pending_bet = None
            self.waiting_for_win = False
            self.waiting_for_losses = False
            return
        self.pending_bet = ghost_signal
        pred_emoji = "🔴" if ghost_signal == 'red' else "🔵"
        if self.on_prediction:
            self.on_prediction(f"🎯 GHOST VALIDADA: {pred_emoji}")
    
    def process_color(self, color: str):
        if not self.active:
            return
        color = self.normalizar_color(color)
        if self.pending_bet is not None:
            is_win = (self.pending_bet == color)
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN", True)
                    self.total_wins += 1
                else:
                    self.on_result(f"❌ LOSS", False)
                    self.total_losses += 1
            self.pending_bet = None
            self.history_window.append(color)
            if is_win:
                self.waiting_for_win = False
                self.waiting_for_losses = False
                self.loss_count = 0
            else:
                self.waiting_for_win = True
                self.waiting_for_losses = False
                self.loss_count = 0
            self._update_status_display(color)
            return
        self.history_window.append(color)
        if self.waiting_for_win:
            if len(self.history_window) >= 2 and list(self.history_window)[-2] != list(self.history_window)[-1]:
                self.waiting_for_win = False
                self.waiting_for_losses = True
                self.loss_count = 0
                if self.on_status:
                    self.on_status(f"👻 WIN detectado - Buscando 1 LOSS...")
            self._update_status_display(color)
            return
        if self.waiting_for_losses:
            if len(self.history_window) >= 2 and list(self.history_window)[-2] == list(self.history_window)[-1]:
                self.loss_count += 1
                if self.loss_count >= 1:
                    self.waiting_for_losses = False
                    self.loss_count = 0
                    if self.on_status:
                        self.on_status("👻 1 LOSS - Validando patrón...")
                    self._execute_ghost_bet()
            else:
                self.loss_count = 0
            self._update_status_display(color)
            return
        self._update_status_display(color)
        if len(self.history_window) >= 5 and self.pending_bet is None and not self.waiting_for_win and not self.waiting_for_losses:
            ghost_signal = list(self.history_window)[-1]
            if self._check_pattern_match(ghost_signal):
                self.pending_bet = ghost_signal
                pred_emoji = "🔴" if ghost_signal == 'red' else "🔵"
                if self.on_prediction:
                    self.on_prediction(f"🎯 GHOST BASE: {pred_emoji}")
    
    def reset(self):
        self.history_window.clear()
        self.pending_bet = None
        self.waiting_for_win = False
        self.waiting_for_losses = False
        self.loss_count = 0

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
        self.user_strategies: Dict[int, object] = {}
        self.running = False
        self.last_processed_index = 0
        self.last_color_time = time.time()
        self.api_url = "https://www.ff2016.vip/api/game/getchart?lang=es"
        self.headers = {"Content-Type": "application/json"}
        self._lock = threading.Lock()
        self.reconnect_timeout = 90
    
    def register_user(self, user_id: int, strategy_type: str, on_status=None, on_prediction=None, on_result=None):
        with self._lock:
            if strategy_type == "standard":
                strategy = StandardStrategy(user_id)
            elif strategy_type == "peakbreak":
                strategy = PeakBreakStrategy(user_id)
            elif strategy_type == "peakhack":
                strategy = HackAlternancia3Strategy(user_id)
            elif strategy_type == "ghost":
                strategy = PeakGhostStrategy(user_id)
            else:
                strategy = StandardStrategy(user_id)
            strategy.on_status = on_status
            strategy.on_prediction = on_prediction
            strategy.on_result = on_result
            self.user_strategies[user_id] = strategy
            return strategy
    
    def unregister_user(self, user_id: int):
        with self._lock:
            if user_id in self.user_strategies:
                self.user_strategies[user_id].active = False
                del self.user_strategies[user_id]
    
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
                                for strategy in self.user_strategies.values():
                                    if strategy.active:
                                        strategy.process_color(last_color)
            except Exception as e:
                print(f"Error en polling: {e}")
            time.sleep(2)

# ==================== BOT DE TELEGRAM ====================
class PredictionBot:
    def __init__(self, token: str):
        self.token = token
        self.license_manager = LicenseManager()
        self.global_polling = GlobalPolling()
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
                print(f"Error: {e}")
    
    def _sync_send_message(self, user_id: int, text: str):
        asyncio.run_coroutine_threadsafe(self._send_message(user_id, text), self.loop)
    
    async def _send_win_image(self, user_id: int):
        try:
            await self.application.bot.send_photo(chat_id=user_id, photo=WIN_IMAGE_URL, caption="✅ WIN WITH THE PEAK BOT")
        except:
            await self._send_message(user_id, "✅ WIN")
    
    def _sync_send_win_image(self, user_id: int):
        asyncio.run_coroutine_threadsafe(self._send_win_image(user_id), self.loop)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)
        if not license_check['valid']:
            keyboard = [
                [InlineKeyboardButton("📅 Estándar 30d - 10 USDT", callback_data='plan_standard')],
                [InlineKeyboardButton("📊 Peak-Break 30d - 15 USDT", callback_data='plan_peakbreak')],
                [InlineKeyboardButton("🔧 Hack Alternancia 30d - 18 USDT", callback_data='plan_peakhack')],
                [InlineKeyboardButton("👻 Ghost 30d - 20 USDT", callback_data='plan_ghost')],
                [InlineKeyboardButton("👥 Multiuser 30d - 45 USDT", callback_data='plan_multiuser')]
            ]
            await update.message.reply_text(
                "🔒 ACCESO RESTRINGIDO\n\nNo tienes licencia activa.\n\n💰 PLANES DISPONIBLES:\n"
                "• 📅 Estándar Mejorado 30d: 10 USDT\n"
                "• 📊 Peak-Break 30d: 15 USDT\n"
                "• 🔧 Peak Hack Alternancia 30d: 18 USDT\n"
                "• 👻 Peak-Ghost 30d: 20 USDT\n"
                "• 👥 Multiuser 30d: 45 USDT\n\n"
                "Selecciona una opción:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        license_data = license_check['data']
        plan_name = LICENSE_PLANS[license_data['plan']]['name']
        max_accounts = license_data.get('max_users', 1)
        keyboard = [
            [InlineKeyboardButton("📡 MODO SEÑALES", callback_data='signals_mode')],
            [InlineKeyboardButton("🤖 MODO AUTOMATICO", callback_data='auto_mode')],
            [InlineKeyboardButton("📜 Info Licencia", callback_data='license_info')],
            [InlineKeyboardButton("💰 Comprar Licencia", callback_data='buy_license')]
        ]
        await update.message.reply_text(
            f"🎰 PREDICTOR PRO BOT\n\n✅ Licencia: {plan_name}\n👥 Máx cuentas: {max_accounts}\n\n"
            f"📊 ESTRATEGIAS DISPONIBLES:\n"
            f"• ESTÁNDAR MEJORADO: Minoría últimos 5\n"
            f"• PEAK-BREAK: Entrar después de 2 LOSS\n"
            f"• PEAK HACK: MISMO color | Alternancia 3 → OPUESTO\n"
            f"• PEAK-GHOST: Validación de patrones\n\n"
            f"Selecciona una opción:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def signals_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)
        if not license_check['valid']:
            await query.edit_message_text("❌ Licencia no válida")
            return
        allowed_mode = license_check['data'].get('mode', 'standard')
        if not self.global_polling.running:
            self.global_polling.start()
        
        def on_status(msg):
            self._sync_send_message(user_id, msg)
        
        def on_prediction(msg):
            self._sync_send_message(user_id, msg)
        
        def on_result(msg, is_win):
            self._sync_send_message(user_id, msg)
            if is_win:
                self._sync_send_win_image(user_id)
        
        strategy_type = allowed_mode if allowed_mode != "flexible" else "standard"
        self.global_polling.register_user(user_id, strategy_type, on_status, on_prediction, on_result)
        self.user_sessions[user_id] = {'mode': 'signals'}
        
        mode_names = {
            'standard': 'ESTÁNDAR MEJORADO',
            'peakbreak': 'PEAK-BREAK',
            'peakhack': 'PEAK HACK (Alternancia)',
            'ghost': 'PEAK-GHOST'
        }
        
        await query.edit_message_text(
            f"📡 MODO SEÑALES ACTIVADO\n\n📊 Estrategia: {mode_names.get(strategy_type, strategy_type.upper())}\n\n"
            f"Recibirás las señales automáticamente.\nEn cada WIN recibirás imagen especial.\n\nUsa /stop para detener."
        )
    
    async def auto_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)
        if not license_check['valid']:
            await query.edit_message_text("❌ No tienes licencia activa")
            return
        license_data = license_check['data']
        max_accounts = license_data.get('max_users', 1)
        allowed_mode = license_data.get('mode', 'standard')
        
        if allowed_mode == "flexible":
            await query.edit_message_text(
                "🤖 MODO AUTOMATICO\n\n📊 SELECCIONA ESTRATEGIA:\n"
                "1️⃣ Estándar Mejorado\n2️⃣ Peak-Break\n3️⃣ Peak Hack (Alternancia)\n4️⃣ Peak-Ghost\n\nEnvía el número:"
            )
            context.user_data['awaiting_strategy_selection'] = True
            context.user_data['max_accounts'] = max_accounts
        else:
            await query.edit_message_text(
                f"🤖 MODO AUTOMATICO\n\n📊 Estrategia asignada: {allowed_mode.upper()}\n\n"
                f"Envía tus credenciales:\nusuario:contraseña\n\nMáx {max_accounts} cuentas: user1:pass1,user2:pass2"
            )
            context.user_data['awaiting_credentials'] = True
            context.user_data['max_accounts'] = max_accounts
            context.user_data['forced_strategy'] = allowed_mode
    
    async def select_strategy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        strategy_map = {"1": "standard", "2": "peakbreak", "3": "peakhack", "4": "ghost"}
        strategy = strategy_map.get(text)
        if not strategy:
            await update.message.reply_text("❌ Opción inválida. Envía 1, 2, 3 o 4")
            return
        context.user_data['selected_strategy'] = strategy
        context.user_data['awaiting_strategy_selection'] = False
        context.user_data['awaiting_credentials'] = True
        
        mode_names = {
            'standard': 'ESTÁNDAR MEJORADO',
            'peakbreak': 'PEAK-BREAK',
            'peakhack': 'PEAK HACK (Alternancia)',
            'ghost': 'PEAK-GHOST'
        }
        
        await update.message.reply_text(
            f"✅ Estrategia seleccionada: {mode_names.get(strategy, strategy.upper())}\n\n"
            f"Envía tus credenciales:\nusuario:contraseña\n\nMáx {context.user_data.get('max_accounts', 1)} cuentas: user1:pass1,user2:pass2"
        )
    
    async def process_credentials(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text
        max_accounts = context.user_data.get('max_accounts', 1)
        strategy = context.user_data.get('selected_strategy', context.user_data.get('forced_strategy', 'standard'))
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
            
            def on_status(msg):
                self._sync_send_message(user_id, msg)
            
            def on_prediction(msg):
                self._sync_send_message(user_id, msg)
                if self.user_sessions.get(user_id, {}).get('auto_betting_active'):
                    color = None
                    if '🔴' in msg:
                        color = 'red'
                    elif '🔵' in msg:
                        color = 'blue'
                    if color:
                        self._execute_bets(user_id, color)
            
            def on_result(msg, is_win):
                self._sync_send_message(user_id, msg)
                if is_win:
                    self._sync_send_win_image(user_id)
                if self.user_sessions.get(user_id, {}).get('auto_betting_active'):
                    self._update_bet_on_result(user_id, is_win)
                    self._show_balances(user_id)
            
            self.global_polling.register_user(user_id, strategy, on_status, on_prediction, on_result)
            self.user_sessions[user_id] = {
                'mode': 'auto',
                'accounts': accounts,
                'auto_betting_active': False,
                'strategy': strategy,
                'bet_config': {
                    'initial_bet': 0.1,
                    'current_bet': 0.1,
                    'max_bet': 10.0,
                    'max_losses': 5,
                    'use_martingale': False,
                }
            }
            await self.show_betting_config(update, user_id)
        else:
            await update.message.reply_text("❌ No se pudo conectar ninguna cuenta")
        context.user_data['awaiting_credentials'] = False
    
    def _execute_bets(self, user_id: int, color: str):
        session = self.user_sessions.get(user_id)
        if not session:
            return
        for account in session.get('accounts', []):
            try:
                if not account.betting_active or account.balance <= 0 or account.current_bet > account.balance:
                    continue
                success, msg = account.place_bet(color, account.current_bet)
                if success:
                    self._sync_send_message(user_id, f"💰 {account.username}: ${account.current_bet:.2f} a {color.upper()}")
                else:
                    self._sync_send_message(user_id, f"❌ {account.username}: {msg}")
            except Exception as e:
                print(f"Error: {e}")
    
    def _update_bet_on_result(self, user_id: int, won: bool):
        session = self.user_sessions.get(user_id)
        if not session:
            return
        for account in session.get('accounts', []):
            if not account.betting_active:
                continue
            if won:
                account.wins += 1
                account.reset_bet()
                self._sync_send_message(user_id, f"💰 {account.username}: WIN - Reiniciada a ${account.current_bet:.2f}")
            else:
                account.losses += 1
                if account.consecutive_losses + 1 >= account.max_consecutive_losses:
                    self._sync_send_message(user_id, f"🛑 {account.username}: Stop loss alcanzado")
                    account.betting_active = False
                else:
                    msg = account.update_bet_on_loss()
                    self._sync_send_message(user_id, f"📉 {account.username}: {msg}")
    
    def _show_balances(self, user_id: int):
        session = self.user_sessions.get(user_id)
        if not session:
            return
        msg = "💰 SALDOS ACTUALIZADOS\n\n"
        for acc in session.get('accounts', []):
            acc.get_balance()
            msg += f"• {acc.username}: ${acc.balance:.2f}\n"
        self._sync_send_message(user_id, msg)
    
    async def show_betting_config(self, update, user_id):
        session = self.user_sessions[user_id]
        config = session['bet_config']
        strategy = session.get('strategy', 'standard')
        
        strategy_names = {
            'standard': 'ESTÁNDAR MEJORADO',
            'peakbreak': 'PEAK-BREAK',
            'peakhack': 'PEAK HACK (Alternancia)',
            'ghost': 'PEAK-GHOST'
        }
        
        keyboard = [
            [InlineKeyboardButton(f"💰 Inicial: ${config['initial_bet']}", callback_data='cfg_initial')],
            [InlineKeyboardButton(f"📈 Máximo: ${config['max_bet']}", callback_data='cfg_max_bet')],
            [InlineKeyboardButton(f"🛑 Max Losses: {config['max_losses']}", callback_data='cfg_max_losses')],
            [InlineKeyboardButton(f"🎲 Modo: {'Martingala' if config['use_martingale'] else 'Agresivo'}", callback_data='cfg_mode')],
            [InlineKeyboardButton("📊 Ver Balances", callback_data='view_balances')],
            [InlineKeyboardButton("▶️ INICIAR AUTO-BET", callback_data='start_autobet')],
            [InlineKeyboardButton("◀️ Volver", callback_data='back_to_start')]
        ]
        
        msg = (f"⚙️ CONFIGURACIÓN DE APUESTAS\n\n"
               f"📊 Estrategia: {strategy_names.get(strategy, strategy.upper())}\n"
               f"💰 Apuesta actual: ${config['current_bet']}\n"
               f"🎲 Modo: {'Martingala (x2)' if config['use_martingale'] else 'Agresivo (x2+inicial)'}\n\n"
               f"Ejemplo con $0.10 inicial:\n"
               f"• Martingala: 0.10 → 0.20 → 0.40 → 0.80\n"
               f"• Agresivo: 0.10 → 0.30 → 0.70 → 1.50")
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    
    async def cfg_mode(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        current = self.user_sessions[user_id]['bet_config']['use_martingale']
        self.user_sessions[user_id]['bet_config']['use_martingale'] = not current
        for acc in self.user_sessions[user_id]['accounts']:
            acc.use_martingale = not current
        await update.callback_query.answer(f"Modo cambiado a {'Martingala' if not current else 'Agresivo'}")
        await self.show_betting_config(update, user_id)
    
    async def cfg_initial(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("💰 Envía nuevo monto inicial (mínimo 0.1):")
        context.user_data['awaiting_initial_bet'] = True
    
    async def cfg_max_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("📈 Envía monto máximo:")
        context.user_data['awaiting_max_bet'] = True
    
    async def cfg_max_losses(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("🛑 Envía número máximo de pérdidas:")
        context.user_data['awaiting_max_losses'] = True
    
    async def process_initial_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            amount = float(update.message.text)
            if amount < 0.1:
                await update.message.reply_text("❌ Mínimo 0.1")
                return
            self.user_sessions[user_id]['bet_config']['initial_bet'] = amount
            self.user_sessions[user_id]['bet_config']['current_bet'] = amount
            for acc in self.user_sessions[user_id]['accounts']:
                acc.initial_bet = amount
                acc.current_bet = amount
            await update.message.reply_text(f"✅ Monto inicial: ${amount:.2f}")
            await self.show_betting_config(update, user_id)
        except:
            await update.message.reply_text("❌ Número inválido")
        context.user_data['awaiting_initial_bet'] = False
    
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
            await update.message.reply_text(f"✅ Max Losses: {value}")
            await self.show_betting_config(update, user_id)
        except:
            await update.message.reply_text("❌ Número inválido")
        context.user_data['awaiting_max_losses'] = False
    
    async def start_autobet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await update.callback_query.answer("❌ No hay cuentas")
            return
        config = self.user_sessions[user_id]['bet_config']
        for acc in self.user_sessions[user_id]['accounts']:
            acc.initial_bet = config['initial_bet']
            acc.current_bet = config['initial_bet']
            acc.max_bet = config['max_bet']
            acc.max_consecutive_losses = config['max_losses']
            acc.use_martingale = config['use_martingale']
            acc.consecutive_losses = 0
            acc.betting_active = True
        self.user_sessions[user_id]['auto_betting_active'] = True
        modo_texto = "Martingala (x2)" if config['use_martingale'] else "Agresivo (x2+inicial)"
        await update.callback_query.edit_message_text(
            f"✅ AUTO-BET ACTIVADO\n\n💰 Inicial: ${config['initial_bet']}\n📈 Máximo: ${config['max_bet']}\n"
            f"🛑 Max Losses: {config['max_losses']}\n🎲 Modo: {modo_texto}\n\nUsa /stop para detener."
        )
    
    async def view_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        session = self.user_sessions.get(user_id)
        if not session:
            await update.callback_query.answer("No hay sesión")
            return
        msg = "💰 BALANCES\n\n"
        for acc in session.get('accounts', []):
            acc.get_balance()
            msg += f"• {acc.username}: ${acc.balance:.2f}\n"
        await update.callback_query.edit_message_text(msg)
    
    async def buy_license(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("📅 Estándar 30d - 10 USDT", callback_data='plan_standard')],
            [InlineKeyboardButton("📊 Peak-Break 30d - 15 USDT", callback_data='plan_peakbreak')],
            [InlineKeyboardButton("🔧 Hack Alternancia 30d - 18 USDT", callback_data='plan_peakhack')],
            [InlineKeyboardButton("👻 Ghost 30d - 20 USDT", callback_data='plan_ghost')],
            [InlineKeyboardButton("👥 Multiuser 30d - 45 USDT", callback_data='plan_multiuser')]
        ]
        await update.callback_query.edit_message_text("💰 COMPRAR LICENCIA\n\nSelecciona un plan:", reply_markup=InlineKeyboardMarkup(keyboard))
    
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
            'plan': plan_id,
            'amount': plan['price'],
            'username': update.effective_user.username or update.effective_user.first_name
        }
        keyboard = [
            [InlineKeyboardButton("📸 Enviar Comprobante", callback_data='send_payment_proof')],
            [InlineKeyboardButton("◀️ Volver", callback_data='back_to_start')]
        ]
        await query.edit_message_text(
            f"💸 PAGO REQUERIDO\n\n📦 Plan: {plan['name']}\n💰 Monto: {plan['price']} USDT (BEP20)\n\n"
            f"📤 Wallet:\n`{MY_WALLET_BEP20}`\n\n1️⃣ Transferir EXACTAMENTE {plan['price']} USDT\n"
            f"2️⃣ Toca 📸 Enviar Comprobante\n3️⃣ Adjunta CAPTURA con TXID\n\n🆔 Tu ID: `{user_id}`",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
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
            f"📸 ENVIA CAPTURA\n\n📦 Plan: {plan_name}\n💰 Monto: {self.pending_payments[user_id]['amount']} USDT\n\n"
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
            f"🆕 NUEVO PAGO\n\n👤 @{username}\n🆔 {user_id}\n📦 {plan_name}\n💰 {amount} USDT\n"
            f"📝 TXID: {txid}\n\n✅ /validar {user_id} {plan_info['plan']}"
        )
        try:
            if update.message.photo:
                photo = update.message.photo[-1]
                await self.application.bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=photo.file_id, caption=admin_msg)
                await update.message.reply_text("✅ Comprobante enviado. En breve será verificado")
                del self.pending_payments[user_id]
            else:
                await update.message.reply_text("❌ Envía una imagen con el comprobante")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {str(e)[:100]}\n\nEnvía manualmente: /validar {user_id} {plan_info['plan']}")
        context.user_data['awaiting_payment_proof'] = False
    
    async def license_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)
        if license_check['valid']:
            data = license_check['data']
            expiry = datetime.fromisoformat(data['expiry'])
            days = (expiry - datetime.now()).days
            await query.edit_message_text(
                f"📜 INFORMACIÓN DE LICENCIA\n\n📋 Plan: {LICENSE_PLANS[data['plan']]['name']}\n"
                f"👥 Modo: {data.get('mode', 'standard').upper()}\n🔢 Máx cuentas: {data.get('max_users', 1)}\n"
                f"📅 Activada: {datetime.fromisoformat(data['activated']).strftime('%Y-%m-%d')}\n"
                f"⏰ Expira: {expiry.strftime('%Y-%m-%d')}\n📆 Días restantes: {days}"
            )
        else:
            await query.edit_message_text("❌ Sin licencia activa")
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.user_sessions:
            self.user_sessions[user_id]['auto_betting_active'] = False
            self.global_polling.unregister_user(user_id)
            del self.user_sessions[user_id]
        await update.message.reply_text("⏹️ Auto-bot detenido")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        context.user_data.clear()
        await update.message.reply_text("❌ Operación cancelada")
    
    async def validate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ No autorizado")
            return
        args = context.args
        if len(args) < 2:
            await update.message.reply_text("📋 USO: /validar USER_ID PLAN\n\nPLANES: standard, peakbreak, peakhack, ghost, multiuser")
            return
        try:
            target_user_id = int(args[0])
            plan = args[1]
            if plan not in LICENSE_PLANS:
                await update.message.reply_text(f"❌ Plan '{plan}' no válido")
                return
            if self.license_manager.activate_license(target_user_id, plan):
                plan_name = LICENSE_PLANS[plan]['name']
                await update.message.reply_text(f"✅ Licencia '{plan_name}' activada para {target_user_id}")
                await self._send_message(
                    target_user_id,
                    f"🎉 ¡LICENCIA ACTIVADA!\n\n📦 Plan: {plan_name}\n📊 Modo: {LICENSE_PLANS[plan]['mode'].upper()}\n"
                    f"👥 Máx cuentas: {LICENSE_PLANS[plan]['max_users']}\n\nUsa /start para comenzar"
                )
            else:
                await update.message.reply_text("❌ Error al activar la licencia")
        except:
            await update.message.reply_text("❌ USER_ID debe ser un número")
    
    async def back_to_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.start_command(update, context)
    
    async def handle_any_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.pending_payments:
            await self.handle_payment_proof(update, context)
        else:
            await update.message.reply_text("📸 No hay compra pendiente. Usa /start")
    
    async def handle_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get('awaiting_strategy_selection'):
            await self.select_strategy(update, context)
        elif context.user_data.get('awaiting_credentials'):
            await self.process_credentials(update, context)
        elif context.user_data.get('awaiting_initial_bet'):
            await self.process_initial_bet(update, context)
        elif context.user_data.get('awaiting_max_bet'):
            await self.process_max_bet(update, context)
        elif context.user_data.get('awaiting_max_losses'):
            await self.process_max_losses(update, context)
        elif context.user_data.get('awaiting_payment_proof'):
            if update.message.photo:
                await self.handle_payment_proof(update, context)
            else:
                await update.message.reply_text("❌ Envía una imagen con el comprobante")
        else:
            await update.message.reply_text("❌ Comando no reconocido. Usa /start")
    
    def run(self):
        self.application = Application.builder().token(self.token).build()
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("stop", self.stop_command))
        self.application.add_handler(CommandHandler("cancel", self.cancel_command))
        self.application.add_handler(CommandHandler("validar", self.validate_command))
        self.application.add_handler(CallbackQueryHandler(self.signals_mode, pattern='signals_mode'))
        self.application.add_handler(CallbackQueryHandler(self.auto_mode, pattern='auto_mode'))
        self.application.add_handler(CallbackQueryHandler(self.buy_license, pattern='buy_license'))
        self.application.add_handler(CallbackQueryHandler(self.select_plan, pattern='plan_'))
        self.application.add_handler(CallbackQueryHandler(self.send_payment_proof, pattern='send_payment_proof'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_initial, pattern='cfg_initial'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_max_bet, pattern='cfg_max_bet'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_max_losses, pattern='cfg_max_losses'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_mode, pattern='cfg_mode'))
        self.application.add_handler(CallbackQueryHandler(self.start_autobet, pattern='start_autobet'))
        self.application.add_handler(CallbackQueryHandler(self.view_balances, pattern='view_balances'))
        self.application.add_handler(CallbackQueryHandler(self.license_info, pattern='license_info'))
        self.application.add_handler(CallbackQueryHandler(self.back_to_start, pattern='back_to_start'))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_messages))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_any_photo))
        
        print("=" * 50)
        print("🤖 PREDICTOR PRO BOT INICIADO - VERSIÓN DEFINITIVA")
        print("=" * 50)
        print("📊 4 MODOS DE ESTRATEGIA:")
        print("  • ESTÁNDAR MEJORADO - Minoría últimos 5")
        print("  • PEAK-BREAK - Entrar después de 2 LOSS")
        print("  • PEAK HACK - MISMO color | Alternancia 3 → OPUESTO")
        print("  • PEAK-GHOST - Validación de patrones")
        print("=" * 50)
        print("✅ AUTO-BET FUNCIONANDO")
        print("🔄 ALTERNANCIA FUNCIONANDO")
        print("🖼️ IMAGEN WIN FUNCIONANDO")
        print("=" * 50)
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    print("🚀 INICIANDO PREDICTOR PRO BOT...")
    bot = PredictionBot(BOT_TOKEN)
    bot.run()