# bot.py - HACK PREDICTOR BOT (VERSIÓN DEFINITIVA)
# PRECIOS: HACK=15, PEAK BREAK=35, MULTIUSER=75
# LÓGICA HACK: BASE (seguir color) → ALTERNANCIA (3 colores) → RUPTURA (4 colores)

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
    "hack": {"price": 15, "days": 30, "mode": "hack", "max_users": 1, "name": "🔧 Hack 30 Días"},
    "multiuser": {"price": 75, "days": 30, "mode": "hack", "max_users": 5, "name": "👥 Multiuser 30 Días"},
    "peakbreak": {"price": 35, "days": 30, "mode": "peakbreak", "max_users": 1, "name": "⛰️ Peak Break 30 Días"},
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

# ==================== USER ACCOUNT (CON TAKE PROFIT) ====================
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
        
        # TAKE PROFIT
        self.initial_balance_snapshot = 0.0
        self.take_profit_amount = 0.0
        
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
    
    def check_take_profit(self) -> bool:
        if self.take_profit_amount <= 0:
            return False
        if self.initial_balance_snapshot <= 0:
            return False
        current_profit = self.balance - self.initial_balance_snapshot
        return current_profit >= self.take_profit_amount
    
    def get_profit_info(self) -> str:
        if self.initial_balance_snapshot <= 0:
            return "Sin snapshot inicial"
        profit = self.balance - self.initial_balance_snapshot
        return f"💰 Inicial: ${self.initial_balance_snapshot:.2f} | Actual: ${self.balance:.2f} | Ganancia: ${profit:.2f}"

# ==================== CUENTA HACK ====================
class HackAccount(UserAccount):
    def __init__(self, username, password):
        super().__init__(username, password)
    
    def get_status(self) -> str:
        return f"💰 ${self.balance:.2f}"

# ==================== PREDICTOR HACK (LÓGICA CORREGIDA: BASE → ALTERNANCIA → RUPTURA) ====================
class HackPredictor:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.history_window = deque(maxlen=20)
        self.active = True
        self.total_wins = 0
        self.total_losses = 0
        self.pending_bet = None
        self.on_prediction = None
        self.on_result = None
        self.estaba_en_alternancia = False  # Para saber si veníamos de alternancia
    
    def _detectar_alternancia(self) -> bool:
        """Detecta si los últimos 3 colores alternan (ej: 🔴🔵🔴 o 🔵🔴🔵)"""
        if len(self.history_window) < 3:
            return False
        ultimos_3 = list(self.history_window)[-3:]
        return ultimos_3[0] != ultimos_3[1] and ultimos_3[1] != ultimos_3[2]
    
    def _detectar_ruptura(self) -> bool:
        """Detecta ruptura: venía alternando y ahora 2 iguales (ej: 🔴🔵🔴🔴)"""
        if len(self.history_window) < 4:
            return False
        ultimos_4 = list(self.history_window)[-4:]
        # Últimos 2 son iguales Y los 3 anteriores alternaban
        return (ultimos_4[-2] == ultimos_4[-1] and 
                ultimos_4[0] != ultimos_4[1] and 
                ultimos_4[1] != ultimos_4[2])
    
    def _calcular_senal(self) -> str:
        if len(self.history_window) == 0:
            return 'red'
        
        ultimo = self.history_window[-1]
        
        # 1º BASE: Por defecto, seguir el color (CONTINUIDAD)
        # Esto es lo que pasa la mayor parte del tiempo
        
        # 2º ¿Hay ALTERNANCIA? (3 colores alternados)
        if self._detectar_alternancia():
            self.estaba_en_alternancia = True
            # Predecir el contrario para seguir alternando
            return 'blue' if ultimo == 'red' else 'red'
        
        # 3º ¿Hay RUPTURA? (se rompió la alternancia)
        if self._detectar_ruptura():
            self.estaba_en_alternancia = False
            # Predecir el contrario (por la ruptura)
            return 'blue' if ultimo == 'red' else 'red'
        
        # Si no hay ni alternancia ni ruptura → BASE
        self.estaba_en_alternancia = False
        return ultimo
    
    def _obtener_logica_usada(self) -> str:
        if self._detectar_ruptura():
            return "RUPTURA"
        if self._detectar_alternancia():
            return "ALTERNANCIA"
        return "BASE"
    
    def _enviar_senal(self):
        if len(self.history_window) == 0:
            return None
        prediction = self._calcular_senal()
        pred_emoji = "🔴" if prediction == 'red' else "🔵"
        logica = self._obtener_logica_usada()
        
        if self.on_prediction:
            self.on_prediction(f"🎯 SEÑAL HACK ({logica}): {pred_emoji}")
        
        return prediction
    
    def process_color(self, color: str):
        if not self.active:
            return
        color = self._normalizar_color(color)
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
        self.pending_bet = self._enviar_senal()
    
    def _normalizar_color(self, color: str) -> str:
        if color is None:
            return 'red'
        c = str(color).lower().strip()
        if c in ['red', 'rojo', '🔴', '1', 'r']:
            return 'red'
        if c in ['blue', 'azul', '🔵', '2', 'b']:
            return 'blue'
        return 'red'
    
    def reset(self):
        self.history_window.clear()
        self.pending_bet = None
        self.total_wins = 0
        self.total_losses = 0
        self.estaba_en_alternancia = False

# ==================== PREDICTOR PEAK BREAK ====================
class PeakBreakPredictor(HackPredictor):
    """
    Modo Peak Break: Solo apuesta después de 3 pérdidas consecutivas.
    Cuando gana, se desactiva y vuelve a esperar 3 pérdidas.
    Cuando pierde, sigue apostando en cada ronda hasta ganar.
    """
    def __init__(self, user_id: int):
        super().__init__(user_id)
        self.consecutive_losses_count = 0
        self.waiting_for_losses = True
        self.in_peak_mode = False
    
    def process_color(self, color: str):
        if not self.active:
            return
        
        color = self._normalizar_color(color)
        
        # ============================================
        # 1. VERIFICAR RESULTADO DE APUESTA ANTERIOR
        # ============================================
        if self.pending_bet is not None:
            is_win = (self.pending_bet == color)
            
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN", True)
                    self.total_wins += 1
                    # GANÓ → Reiniciar completamente
                    self.in_peak_mode = False
                    self.waiting_for_losses = True
                    self.consecutive_losses_count = 0
                    self.pending_bet = None
                    if self.on_prediction:
                        self.on_prediction(f"⛰️ PEAK BREAK: WIN - Volviendo a esperar 3 pérdidas")
                    self.history_window.append(color)
                    return
                else:
                    self.on_result(f"❌ LOSS", False)
                    self.total_losses += 1
                    # PERDIÓ → Seguir en modo peak
                    self.in_peak_mode = True
                    self.waiting_for_losses = False
                    self.pending_bet = None
        
        # ============================================
        # 2. AGREGAR COLOR AL HISTORIAL
        # ============================================
        self.history_window.append(color)
        
        # ============================================
        # 3. LÓGICA PEAK BREAK
        # ============================================
        
        # MODO 1: Esperando 3 pérdidas consecutivas
        if self.waiting_for_losses:
            if len(self.history_window) >= 2:
                anterior = self.history_window[-2]
                if anterior != color:
                    self.consecutive_losses_count += 1
                    if self.on_prediction:
                        self.on_prediction(f"⛰️ PEAK BREAK: Pérdida {self.consecutive_losses_count}/3")
                else:
                    self.consecutive_losses_count = 0
            
            if self.consecutive_losses_count >= 3:
                self.waiting_for_losses = False
                self.in_peak_mode = True
                self.consecutive_losses_count = 0
                
                # Usar lógica HACK para la primera apuesta
                prediction = self._calcular_senal()
                pred_emoji = "🔴" if prediction == 'red' else "🔵"
                logica = self._obtener_logica_usada()
                
                if self.on_prediction:
                    self.on_prediction(f"⛰️ 🔥 PEAK BREAK ACTIVADO - 3 pérdidas consecutivas!")
                    self.on_prediction(f"🎯 APOSTAR ({logica}): {pred_emoji}")
                
                self.pending_bet = prediction
            return
        
        # MODO 2: En peak mode (seguimiento - usa lógica HACK)
        if self.in_peak_mode:
            prediction = self._calcular_senal()
            pred_emoji = "🔴" if prediction == 'red' else "🔵"
            logica = self._obtener_logica_usada()
            
            if self.on_prediction:
                self.on_prediction(f"⛰️ PEAK BREAK (seguimiento - {logica}): {pred_emoji}")
            
            self.pending_bet = prediction

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
        self.user_predictors: Dict[int, HackPredictor] = {}
        self.running = False
        self.last_processed_index = 0
        self.last_color_time = time.time()
        self.api_url = "https://www.ff2016.vip/api/game/getchart?lang=es"
        self.headers = {"Content-Type": "application/json"}
        self._lock = threading.Lock()
        self.reconnect_timeout = 90
    
    def register_user(self, user_id: int, mode: str = "hack", on_prediction=None, on_result=None):
        with self._lock:
            if mode == "peakbreak":
                predictor = PeakBreakPredictor(user_id)
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
            await self.application.bot.send_photo(chat_id=user_id, photo=WIN_IMAGE_URL, caption="✅ WIN")
        except:
            await self._send_message(user_id, "✅ WIN")
    
    def _sync_send_win_image(self, user_id: int):
        asyncio.run_coroutine_threadsafe(self._send_win_image(user_id), self.loop)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)
        
        if not license_check['valid']:
            keyboard = [
                [InlineKeyboardButton("🔧 Hack 30d - 15 USDT", callback_data='plan_hack')],
                [InlineKeyboardButton("👥 Multiuser 30d - 75 USDT", callback_data='plan_multiuser')],
                [InlineKeyboardButton("⛰️ Peak Break 30d - 35 USDT", callback_data='plan_peakbreak')]
            ]
            await update.message.reply_text(
                "🔒 ACCESO RESTRINGIDO\n\nNo tienes licencia activa.\n\n"
                "💰 PLANES DISPONIBLES:\n"
                "• 🔧 Hack 30d: 15 USDT (1 cuenta, apuesta en cada señal)\n"
                "• 👥 Multiuser 30d: 75 USDT (5 cuentas, apuesta en cada señal)\n"
                "• ⛰️ Peak Break 30d: 35 USDT (1 cuenta, apuesta tras 3 pérdidas)\n\n"
                "Selecciona una opción:",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        
        license_data = license_check['data']
        plan_name = LICENSE_PLANS[license_data['plan']]['name']
        max_accounts = license_data.get('max_users', 1)
        mode = license_data.get('mode', 'hack')
        
        modo_texto = "⚡ HACK (apuesta en cada señal)" if mode == "hack" else "⛰️ PEAK BREAK (espera 3 pérdidas)"
        
        keyboard = [
            [InlineKeyboardButton("📡 MODO SEÑALES", callback_data='signals_mode')],
            [InlineKeyboardButton("🤖 MODO AUTOMATICO", callback_data='auto_mode')],
            [InlineKeyboardButton("📜 Info Licencia", callback_data='license_info')],
            [InlineKeyboardButton("💰 Comprar Licencia", callback_data='buy_license')]
        ]
        
        await update.message.reply_text(
            f"🎰 HACK PREDICTOR BOT\n\n✅ Licencia: {plan_name}\n🎲 Modo: {modo_texto}\n👥 Máx cuentas: {max_accounts}\n\n"
            f"Selecciona una opción:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
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
        
        self.global_polling.register_user(user_id, mode, on_prediction, on_result)
        self.user_sessions[user_id] = {'mode': 'signals'}
        
        modo_nombre = "HACK" if mode == "hack" else "PEAK BREAK"
        await query.edit_message_text(
            f"📡 MODO SEÑALES ACTIVADO - {modo_nombre}\n\n"
            f"Recibirás las señales automáticamente.\n"
            f"En cada WIN recibirás imagen especial.\n\n"
            f"Usa /stop para detener."
        )
    
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
        
        modo_nombre = "HACK" if mode == "hack" else "PEAK BREAK"
        
        await query.edit_message_text(
            f"🤖 MODO AUTOMATICO - {modo_nombre}\n\n"
            f"Envía tus credenciales:\n"
            f"usuario:contraseña\n\n"
            f"Máx {max_accounts} cuentas: user1:pass1,user2:pass2"
        )
        context.user_data['awaiting_credentials'] = True
        context.user_data['max_accounts'] = max_accounts
        context.user_data['mode'] = mode
    
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
            acc = HackAccount(username, password)
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
                        color = 'red'
                    elif '🔵' in msg:
                        color = 'blue'
                    else:
                        color = None
                    if color:
                        self._execute_bets(user_id, color)
            
            def on_result(msg, is_win):
                self._sync_send_message(user_id, msg)
                if is_win:
                    self._sync_send_win_image(user_id)
                if self.user_sessions.get(user_id, {}).get('auto_betting_active'):
                    self._update_bet_on_result(user_id, is_win)
                    self._show_balances(user_id)
            
            self.global_polling.register_user(user_id, mode, on_prediction, on_result)
            
            self.user_sessions[user_id] = {
                'mode': 'auto',
                'accounts': accounts,
                'auto_betting_active': False,
                'bot_mode': mode,
                'bet_config': {
                    'initial_bet': 0.1,
                    'current_bet': 0.1,
                    'max_bet': 10.0,
                    'max_losses': 5,
                    'use_martingale': False,
                    'take_profit': 0.0,
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
            if not account.betting_active or account.balance <= 0:
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
                
                # VERIFICAR TAKE PROFIT
                if account.check_take_profit():
                    account.betting_active = False
                    profit_info = account.get_profit_info()
                    self._sync_send_message(user_id, f"🎯 ¡TAKE PROFIT ALCANZADO! {account.username}\n{profit_info}\n🛑 Apuestas detenidas para esta cuenta")
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
        
        msg = "💰 SALDOS\n\n"
        for acc in session.get('accounts', []):
            acc.get_balance()
            msg += f"• {acc.username}: ${acc.balance:.2f}\n"
            if acc.take_profit_amount > 0 and acc.initial_balance_snapshot > 0:
                profit = acc.balance - acc.initial_balance_snapshot
                msg += f"  📈 Meta: ${acc.take_profit_amount:.2f} | Ganancia: ${profit:.2f}\n"
        
        self._sync_send_message(user_id, msg)
    
    async def show_betting_config(self, update, user_id):
        session = self.user_sessions[user_id]
        config = session['bet_config']
        bot_mode = session.get('bot_mode', 'hack')
        
        take_profit_val = config.get('take_profit', 0)
        if take_profit_val == 0:
            tp_display = "DESACTIVADO"
        else:
            tp_display = f"${take_profit_val}"
        
        modo_texto = "⚡ HACK (apuesta en cada señal)" if bot_mode == "hack" else "⛰️ PEAK BREAK (espera 3 pérdidas, luego apuesta hasta ganar)"
        
        keyboard = [
            [InlineKeyboardButton(f"💰 Inicial: ${config['initial_bet']}", callback_data='cfg_initial')],
            [InlineKeyboardButton(f"📈 Máximo: ${config['max_bet']}", callback_data='cfg_max_bet')],
            [InlineKeyboardButton(f"🛑 Max Losses: {config['max_losses']}", callback_data='cfg_max_losses')],
            [InlineKeyboardButton(f"🎲 Modo: {'Martingala' if config['use_martingale'] else 'Agresivo'}", callback_data='cfg_mode')],
            [InlineKeyboardButton(f"🎯 Take Profit: {tp_display}", callback_data='cfg_take_profit')],
            [InlineKeyboardButton("📊 Ver Balances", callback_data='view_balances')],
            [InlineKeyboardButton("▶️ INICIAR AUTO-BET", callback_data='start_autobet')],
            [InlineKeyboardButton("◀️ Volver", callback_data='back_to_start')]
        ]
        
        tp_texto = "DESACTIVADO" if config.get('take_profit', 0) == 0 else f"${config.get('take_profit', 0)}"
        
        msg = (f"⚙️ CONFIGURACIÓN\n\n"
               f"🎲 Estrategia del bot: {modo_texto}\n"
               f"💰 Apuesta actual: ${config['current_bet']}\n"
               f"🎲 Modo gestión: {'Martingala (x2)' if config['use_martingale'] else 'Agresivo (x2+inicial)'}\n"
               f"🎯 Take Profit: {tp_texto}\n\n"
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
        mode = "Martingala (x2)" if not current else "Agresivo (x2+inicial)"
        await update.callback_query.answer(f"Modo cambiado a {mode}")
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
    
    async def cfg_take_profit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "🎯 CONFIGURAR TAKE PROFIT\n\n"
            "Envía el monto de GANANCIA que quieres obtener antes de detener la cuenta.\n\n"
            "Ejemplos:\n"
            "• 5   → Detener cuando ganes $5\n"
            "• 10  → Detener cuando ganes $10\n"
            "• 0   → DESACTIVAR Take Profit\n\n"
            "Envía el número ahora:"
        )
        context.user_data['awaiting_take_profit'] = True
    
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
    
    async def process_take_profit(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        try:
            amount = float(update.message.text)
            if amount < 0:
                await update.message.reply_text("❌ El monto no puede ser negativo")
                return
            
            self.user_sessions[user_id]['bet_config']['take_profit'] = amount
            
            if amount == 0:
                await update.message.reply_text(f"✅ Take Profit DESACTIVADO")
            else:
                await update.message.reply_text(f"✅ Take Profit configurado: ${amount:.2f}\n\nCuando una cuenta gane ${amount:.2f} desde su saldo inicial, se detendrá automáticamente.")
            
            await self.show_betting_config(update, user_id)
        except:
            await update.message.reply_text("❌ Número inválido. Envía un número como 5, 10 o 0 para desactivar")
        context.user_data['awaiting_take_profit'] = False
    
    async def start_autobet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in self.user_sessions:
            await update.callback_query.answer("❌ No hay cuentas")
            return
        
        config = self.user_sessions[user_id]['bet_config']
        bot_mode = self.user_sessions[user_id].get('bot_mode', 'hack')
        take_profit_amount = config.get('take_profit', 0)
        
        for acc in self.user_sessions[user_id]['accounts']:
            acc.initial_bet = config['initial_bet']
            acc.current_bet = config['initial_bet']
            acc.max_bet = config['max_bet']
            acc.max_consecutive_losses = config['max_losses']
            acc.use_martingale = config['use_martingale']
            acc.consecutive_losses = 0
            acc.betting_active = True
            
            # Guardar snapshot del saldo inicial y TP
            acc.get_balance()
            acc.initial_balance_snapshot = acc.balance
            acc.take_profit_amount = take_profit_amount
        
        self.user_sessions[user_id]['auto_betting_active'] = True
        
        modo_texto = "Martingala (x2)" if config['use_martingale'] else "Agresivo (x2+inicial)"
        estrategia_texto = "PEAK BREAK (espera 3 pérdidas)" if bot_mode == "peakbreak" else "HACK (apuesta en cada señal)"
        tp_texto = f"${take_profit_amount}" if take_profit_amount > 0 else "DESACTIVADO"
        
        await update.callback_query.edit_message_text(
            f"✅ AUTO-BET ACTIVADO\n\n"
            f"🎲 Estrategia: {estrategia_texto}\n"
            f"💰 Inicial: ${config['initial_bet']}\n"
            f"📈 Máximo: ${config['max_bet']}\n"
            f"🛑 Max Losses: {config['max_losses']}\n"
            f"🎲 Gestión: {modo_texto}\n"
            f"🎯 Take Profit: {tp_texto}\n"
            f"📊 Cuentas: {len(self.user_sessions[user_id]['accounts'])}\n\n"
            f"Usa /stop para detener."
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
            if acc.take_profit_amount > 0 and acc.initial_balance_snapshot > 0:
                profit = acc.balance - acc.initial_balance_snapshot
                msg += f"  📈 Inicial: ${acc.initial_balance_snapshot:.2f} | Meta: +${acc.take_profit_amount:.2f} | Ganancia: ${profit:.2f}\n"
        
        await update.callback_query.edit_message_text(msg)
    
    async def buy_license(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔧 Hack 30d - 15 USDT", callback_data='plan_hack')],
            [InlineKeyboardButton("👥 Multiuser 30d - 75 USDT", callback_data='plan_multiuser')],
            [InlineKeyboardButton("⛰️ Peak Break 30d - 35 USDT", callback_data='plan_peakbreak')]
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
            'plan': plan_id,
            'amount': plan['price'],
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
            f"1️⃣ Transferir EXACTAMENTE {plan['price']} USDT\n"
            f"2️⃣ Toca 📸 Enviar Comprobante\n"
            f"3️⃣ Adjunta CAPTURA con TXID\n\n"
            f"🆔 Tu ID: `{user_id}`",
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
            f"👤 @{username}\n"
            f"🆔 {user_id}\n"
            f"📦 {plan_name}\n"
            f"💰 {amount} USDT\n"
            f"📝 TXID: {txid}\n\n"
            f"✅ /validar {user_id} {plan_info['plan']}"
        )
        
        try:
            if update.message.photo:
                photo = update.message.photo[-1]
                await self.application.bot.send_photo(
                    chat_id=ADMIN_GROUP_ID,
                    photo=photo.file_id,
                    caption=admin_msg
                )
                await update.message.reply_text("✅ Comprobante enviado. En breve será verificado")
                del self.pending_payments[user_id]
            else:
                await update.message.reply_text("❌ Envía una imagen con el comprobante")
                return
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
            mode = data.get('mode', 'hack')
            modo_texto = "HACK (apuesta en cada señal)" if mode == "hack" else "PEAK BREAK (espera 3 pérdidas)"
            await query.edit_message_text(
                f"📜 INFORMACIÓN DE LICENCIA\n\n"
                f"📋 Plan: {LICENSE_PLANS[data['plan']]['name']}\n"
                f"🎲 Modo: {modo_texto}\n"
                f"🔢 Máx cuentas: {data.get('max_users', 1)}\n"
                f"📅 Activada: {datetime.fromisoformat(data['activated']).strftime('%Y-%m-%d')}\n"
                f"⏰ Expira: {expiry.strftime('%Y-%m-%d')}\n"
                f"📆 Días restantes: {days}"
            )
        else:
            await query.edit_message_text("❌ Sin licencia activa. Usa /start")
    
    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id in self.user_sessions:
            self.user_sessions[user_id]['auto_betting_active'] = False
            self.global_polling.unregister_user(user_id)
            del self.user_sessions[user_id]
        await update.message.reply_text("⏹️ Auto-bot detenido. Usa /start para volver.")
    
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
                "PLANES DISPONIBLES:\n"
                "• hack - Hack 30 días (15 USDT)\n"
                "• multiuser - Multiuser 30 días (75 USDT)\n"
                "• peakbreak - Peak Break 30 días (35 USDT)\n\n"
                "Ejemplo: /validar 123456789 hack"
            )
            return
        
        try:
            target_user_id = int(args[0])
            plan = args[1]
            
            if plan not in LICENSE_PLANS:
                await update.message.reply_text(f"❌ Plan '{plan}' no válido")
                return
            
            if self.license_manager.activate_license(target_user_id, plan):
                plan_name = LICENSE_PLANS[plan]['name']
                await update.message.reply_text(f"✅ Licencia '{plan_name}' activada para usuario {target_user_id}")
                
                await self._send_message(
                    target_user_id,
                    f"🎉 ¡LICENCIA ACTIVADA!\n\n"
                    f"📦 Plan: {plan_name}\n"
                    f"👥 Máx cuentas: {LICENSE_PLANS[plan]['max_users']}\n"
                    f"🎲 Modo: {'HACK' if LICENSE_PLANS[plan]['mode'] == 'hack' else 'PEAK BREAK'}\n\n"
                    f"✅ Ya puedes usar el bot.\n\n"
                    f"Usa /start para comenzar."
                )
            else:
                await update.message.reply_text("❌ Error al activar la licencia")
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
            await update.message.reply_text(
                "📸 No hay ninguna compra pendiente.\n\n"
                "Para comprar una licencia usa /start y selecciona '💰 Comprar Licencia'"
            )
    
    async def handle_messages(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if context.user_data.get('awaiting_credentials'):
            await self.process_credentials(update, context)
        elif context.user_data.get('awaiting_initial_bet'):
            await self.process_initial_bet(update, context)
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
            await update.message.reply_text(
                "❌ Comando no reconocido.\n\n"
                "Usa /start para ver las opciones disponibles."
            )
    
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
        self.application.add_handler(CallbackQueryHandler(self.cfg_take_profit, pattern='cfg_take_profit'))
        self.application.add_handler(CallbackQueryHandler(self.cfg_mode, pattern='cfg_mode'))
        self.application.add_handler(CallbackQueryHandler(self.start_autobet, pattern='start_autobet'))
        self.application.add_handler(CallbackQueryHandler(self.view_balances, pattern='view_balances'))
        self.application.add_handler(CallbackQueryHandler(self.license_info, pattern='license_info'))
        self.application.add_handler(CallbackQueryHandler(self.back_to_start, pattern='back_to_start'))
        
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_messages))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_any_photo))
        
        print("=" * 50)
        print("🤖 HACK PREDICTOR BOT V2 - LÓGICA DEFINITIVA")
        print("=" * 50)
        print("💰 PLANES:")
        print("  • Hack 30d: 15 USDT (1 cuenta)")
        print("  • Multiuser 30d: 75 USDT (5 cuentas)")
        print("  • Peak Break 30d: 35 USDT (1 cuenta)")
        print("=" * 50)
        print("🎯 LÓGICA HACK (orden correcto):")
        print("  1º BASE: Seguir el color que sale")
        print("  2º ALTERNANCIA: 3 colores alternados (🔴🔵🔴 o 🔵🔴🔵)")
        print("  3º RUPTURA: 4 colores (venía alternando y 2 iguales)")
        print("=" * 50)
        print("🎯 OTRAS FUNCIONES:")
        print("  • Take Profit (monto fijo por cuenta)")
        print("  • Peak Break: después de WIN, espera 3 pérdidas")
        print("=" * 50)
        print("✅ BOT LISTO")
        print("=" * 50)
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    print("🚀 INICIANDO...")
    bot = PredictionBot(BOT_TOKEN)
    bot.run()