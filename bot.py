# bot.py - PREDICTOR BOT V7 (DEFINITIVO)
# HACK + PEAK BREAK V2 + CAZADOR + TENDENCIAL + PRO
# CON SISTEMA DE PAUSA Y REINICIO CON RECUPERACIÓN DE SALDO
# CON SISTEMA DE APUESTA PENDIENTE PARA EVITAR ERRORES INTERMITENTES
# COPYRIGHT © 2025 - PRO PREDICTOR

import json
import os
import threading
import time
import requests
import asyncio
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# ==================== CONFIGURACIÓN ====================
BOT_TOKEN = "8758409892:AAElGrpay6Kw5MvRL1TBfQRcK4omW63iQSQ"
ADMIN_IDS = [8051843698]
ADMIN_GROUP_ID = -1003731875494
MY_WALLET_BEP20 = "0x621917958C7ac81190e9f876C23D6B9914f31263"

# IMAGENES
WIN_IMAGE_URL = "https://i.postimg.cc/T2pH8v1q/1777831023149.png"
TAKE_PROFIT_IMAGE_URL = "https://i.postimg.cc/Pf88n71y/1778974518057.png"

# ==================== PLANES DE LICENCIA ====================
LICENSE_PLANS = {
    "hack": {"price": 15, "days": 30, "max_users": 1, "name": "🔧 Hack 30 Días", "mode": "hack"},
    "peakbreak": {"price": 35, "days": 60, "max_users": 1, "name": "⛰️ Peak Break 60 Días", "mode": "peakbreak"},
    "cazador": {"price": 50, "days": 90, "max_users": 1, "name": "🎯 Cazador 90 Días", "mode": "cazador"},
    "tendencial": {"price": 45, "days": 75, "max_users": 1, "name": "📊 Tendencial 75 Días", "mode": "tendencial"},
    "pro": {"price": 60, "days": 90, "max_users": 1, "name": "🏆 PRO 90 Días", "mode": "pro"},
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
            "expiry": expiry_date.isoformat(),
            "max_users": plan_config["max_users"], "active": True,
            "mode": plan_config["mode"]
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
        self.initial_bet_original = 0.1
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
        
        # SISTEMA DE PAUSA Y REINICIO
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
    
    # ==================== SISTEMA DE PAUSA Y REINICIO ====================
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
        
        # SISTEMA DE APUESTA PENDIENTE
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None
    
    def _normalizar_color(self, color: str) -> str:
        if color is None:
            return 'red'
        c = str(color).lower().strip()
        if c in ['red', 'rojo', '🔴', '1', 'r']:
            return 'red'
        if c in ['blue', 'azul', '🔵', '2', 'b']:
            return 'blue'
        return 'red'
    
    def process_color(self, color: str):
        if not self.active:
            return
        
        color = self._normalizar_color(color)
        
        # ============================================
        # 1. VERIFICAR APUESTA PENDIENTE
        # ============================================
        if self.apuesta_pendiente and self.prediccion_pendiente is not None:
            is_win = (self.prediccion_pendiente == color)
            
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN", True)
                    self.consecutive_wins += 1
                    self.consecutive_losses = 0
                    
                    if self.anti_mode:
                        self.anti_mode = False
                        self.anti_rounds_left = 0
                        self.anti_color = None
                        self.first_lost_color = None
                        self.second_lost_color = None
                else:
                    self.on_result(f"❌ LOSS", False)
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0
            
            self.apuesta_pendiente = False
            self.prediccion_pendiente = None
            return
        
        # ============================================
        # 2. AGREGAR COLOR AL HISTORIAL
        # ============================================
        self.session_history.append(color)
        if len(self.session_history) > 20:
            self.session_history = self.session_history[-20:]
        
        # ============================================
        # 3. MANEJO DEL MODO ANTI
        # ============================================
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
        
        # ============================================
        # 4. DETECTAR PÉRDIDAS PARA ACTIVAR MODO ANTI
        # ============================================
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
        
        # ============================================
        # 5. ESTRATEGIA NORMAL: SEGUIR EL ÚLTIMO COLOR
        # ============================================
        if self.session_history:
            last_color = self.session_history[-1]
            prediccion = last_color
            
            self.prediccion_pendiente = prediccion
            self.apuesta_pendiente = True
            self.last_prediction = prediccion
            
            if self.on_prediction:
                self.on_prediction(f"🎯 SIGUIENTE: {'🔴' if last_color == 'red' else '🔵'}")
    
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

# ==================== PREDICTOR PEAK BREAK V2 ====================
class PeakBreakPredictorV2:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.hack_predictor = HackPredictor(user_id)
        self.active = True
        self.on_prediction = None
        self.on_result = None
        
        self.active_mode = False
        self.waiting_for_win = True
        self.last_bet_prediction = None
        self.pending_bet = False
        self.last_winner_color = None
        
        self.required_losses = 1
        self.win_detected = False
        self.losses_count = 0
        
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None
    
    def _normalizar_color(self, color: str) -> str:
        return self.hack_predictor._normalizar_color(color)
    
    def process_color(self, color: str):
        if not self.active:
            return
        
        color = self._normalizar_color(color)
        
        # ============================================
        # 1. VERIFICAR APUESTA PENDIENTE
        # ============================================
        if self.apuesta_pendiente and self.prediccion_pendiente is not None:
            is_win = (self.prediccion_pendiente == color)
            
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN (PEAK BREAK)", True)
                    self.active_mode = True
                    self.waiting_for_win = False
                    self.last_winner_color = color
                    self.win_detected = False
                    self.losses_count = 0
                    self.required_losses = 1
                else:
                    self.on_result(f"❌ LOSS (PEAK BREAK)", False)
                    self.active_mode = False
                    self.waiting_for_win = True
                    self.last_winner_color = None
                    self.win_detected = False
                    self.losses_count = 0
                    self.required_losses = 1
            
            self.apuesta_pendiente = False
            self.prediccion_pendiente = None
            return
        
        # ============================================
        # 2. ACTUALIZAR PREDICTOR HACK
        # ============================================
        previous_prediction = self.hack_predictor.get_last_prediction()
        self.hack_predictor.process_color(color)
        
        # ============================================
        # 3. LÓGICA DE ACTIVACIÓN: WIN + N LOSS
        # ============================================
        if not self.active_mode and self.waiting_for_win and not self.apuesta_pendiente:
            if previous_prediction is not None and previous_prediction == color:
                self.win_detected = True
                self.losses_count = 0
                if self.on_prediction:
                    self.on_prediction(f"🔍 WIN detectado - Buscando {self.required_losses} LOSS para activar")
            
            elif self.win_detected and not (previous_prediction is not None and previous_prediction == color):
                self.losses_count += 1
                if self.on_prediction:
                    self.on_prediction(f"🔍 LOSS {self.losses_count}/{self.required_losses}")
                
                if self.losses_count >= self.required_losses:
                    self.active_mode = True
                    self.waiting_for_win = False
                    self.last_winner_color = None
                    self.win_detected = False
                    self.losses_count = 0
                    
                    if self.required_losses == 1:
                        self.required_losses = 2
                    else:
                        self.required_losses = 1
                    
                    if self.on_prediction:
                        self.on_prediction(f"⛰️ PEAK BREAK ACTIVADO! (WIN + {self.required_losses} LOSS)")
            
            elif not self.win_detected:
                self.losses_count = 0
        
        # ============================================
        # 4. GENERAR APUESTA SI ESTAMOS ACTIVOS
        # ============================================
        if self.active_mode and not self.apuesta_pendiente:
            if self.hack_predictor.last_prediction:
                pred = self.hack_predictor.last_prediction
            else:
                pred = self.hack_predictor.get_last_prediction()
            
            if pred:
                self.prediccion_pendiente = pred
                self.apuesta_pendiente = True
                self.last_bet_prediction = pred
                
                pred_emoji = "🔴" if pred == 'red' else "🔵"
                if self.on_prediction:
                    self.on_prediction(f"⛰️ PEAK BREAK: {pred_emoji}")
    
    def reset(self):
        self.hack_predictor.reset()
        self.active_mode = False
        self.waiting_for_win = True
        self.last_bet_prediction = None
        self.pending_bet = False
        self.last_winner_color = None
        self.required_losses = 1
        self.win_detected = False
        self.losses_count = 0
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None

# ==================== PREDICTOR CAZADOR ====================
class CazadorPredictor:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.active = True
        self.on_prediction = None
        self.on_result = None
        
        self.ultimos_colores = []
        self.estado = "BUSCANDO"
        self.patron_color = None
        self.patron_tipo = None
        self.apuesta_pendiente = False
        self.apuesta_color = None
        self.esperando_resultado = False
        self.primer_cambio_detectado = False
        self.color_bloqueado = None
        
        self.prediccion_pendiente = None
        self.resultado_pendiente = False
    
    def _normalizar_color(self, color: str) -> str:
        if color is None:
            return 'red'
        c = str(color).lower().strip()
        if c in ['red', 'rojo', '🔴', '1', 'r']:
            return 'red'
        if c in ['blue', 'azul', '🔵', '2', 'b']:
            return 'blue'
        return 'red'
    
    def _color_emoji(self, color: str) -> str:
        return "🔴" if color == 'red' else "🔵"
    
    def _color_contrario(self, color: str) -> str:
        return 'blue' if color == 'red' else 'red'
    
    def _buscar_patron(self, colores, color_bloqueado=None):
        if len(colores) < 2:
            return None, None
        
        if len(colores) >= 3:
            for i in range(len(colores) - 3, -1, -1):
                color = colores[i]
                if color_bloqueado is not None and color == color_bloqueado:
                    continue
                if colores[i] == colores[i+1] == colores[i+2]:
                    return color, "triple"
        
        for i in range(len(colores) - 2, -1, -1):
            color = colores[i]
            if color_bloqueado is not None and color == color_bloqueado:
                continue
            if colores[i] == colores[i+1]:
                return color, "doble"
        
        return None, None
    
    def process_color(self, color: str):
        if not self.active:
            return
        
        color = self._normalizar_color(color)
        
        # ============================================
        # 1. VERIFICAR APUESTA PENDIENTE
        # ============================================
        if self.resultado_pendiente and self.prediccion_pendiente is not None:
            is_win = (self.prediccion_pendiente == color)
            
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN (CAZADOR)", True)
                else:
                    self.on_result(f"❌ LOSS (CAZADOR)", False)
            
            if self.estado == "DOBLE" and not is_win:
                if self.on_prediction:
                    self.on_prediction(f"🔄 DOBLE falló - Activando TRIPLE: {self._color_emoji(self.patron_color)}")
                self.estado = "TRIPLE"
                self.patron_tipo = "triple"
                self.apuesta_pendiente = False
                self.resultado_pendiente = False
                self.apuesta_color = None
                self.prediccion_pendiente = None
                self._generar_apuesta()
                return
            
            else:
                if self.on_prediction:
                    if is_win:
                        self.on_prediction("✅ Patrón completado - Buscando nuevo patrón")
                    else:
                        self.on_prediction("❌ Patrón falló - Buscando nuevo patrón")
                
                if self.patron_color is not None:
                    self.color_bloqueado = self.patron_color
                    if self.on_prediction:
                        self.on_prediction(f"🚫 BLOQUEADO: {self._color_emoji(self.color_bloqueado)} (esperando {self._color_emoji(self._color_contrario(self.color_bloqueado))})")
                
                self.estado = "BUSCANDO"
                self.patron_color = None
                self.patron_tipo = None
                self.apuesta_pendiente = False
                self.resultado_pendiente = False
                self.apuesta_color = None
                self.prediccion_pendiente = None
                return
        
        # ============================================
        # 2. AGREGAR COLOR AL HISTORIAL
        # ============================================
        self.ultimos_colores.append(color)
        if len(self.ultimos_colores) > 20:
            self.ultimos_colores = self.ultimos_colores[-20:]
        
        # ============================================
        # 3. ESPERAR EL PRIMER CAMBIO DE COLOR
        # ============================================
        if not self.primer_cambio_detectado:
            if len(self.ultimos_colores) >= 2:
                if self.ultimos_colores[-1] != self.ultimos_colores[-2]:
                    self.primer_cambio_detectado = True
                    if self.on_prediction:
                        self.on_prediction("🔍 CAZADOR ACTIVADO - Buscando patrones")
            if not self.primer_cambio_detectado:
                return
        
        # ============================================
        # 4. BUSCAR PATRONES
        # ============================================
        if not self.apuesta_pendiente and not self.resultado_pendiente and self.estado == "BUSCANDO":
            patron_color, patron_tipo = self._buscar_patron(self.ultimos_colores, self.color_bloqueado)
            
            if patron_color is not None:
                self.patron_color = patron_color
                self.patron_tipo = patron_tipo
                
                if patron_tipo == "triple":
                    self.estado = "TRIPLE"
                    if self.on_prediction:
                        self.on_prediction(f"🎯 TRIPLE detectado: {self._color_emoji(patron_color)}{self._color_emoji(patron_color)}{self._color_emoji(patron_color)}")
                else:
                    self.estado = "DOBLE"
                    if self.on_prediction:
                        self.on_prediction(f"🎯 DOBLE detectado: {self._color_emoji(patron_color)}{self._color_emoji(patron_color)}")
                
                self._generar_apuesta()
    
    def _generar_apuesta(self):
        if self.patron_color is None:
            return
        
        self.apuesta_color = self._color_contrario(self.patron_color)
        self.apuesta_pendiente = True
        self.resultado_pendiente = True
        self.prediccion_pendiente = self.apuesta_color
        
        emoji = self._color_emoji(self.apuesta_color)
        if self.patron_tipo == "doble":
            self.on_prediction(f"🎯 CAZADOR (DOBLE → {emoji})")
        else:
            self.on_prediction(f"🎯 CAZADOR (TRIPLE → {emoji})")
    
    def reset(self):
        self.ultimos_colores = []
        self.estado = "BUSCANDO"
        self.patron_color = None
        self.patron_tipo = None
        self.apuesta_pendiente = False
        self.apuesta_color = None
        self.resultado_pendiente = False
        self.primer_cambio_detectado = False
        self.color_bloqueado = None
        self.prediccion_pendiente = None

# ==================== PREDICTOR TENDENCIAL ====================
class TendencialPredictor:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.active = True
        self.on_prediction = None
        self.on_result = None
        
        self.estado = "ESPERANDO"
        self.primer_color = None
        self.ciclo_actual = None
        self.rondas_actuales = 0
        self.color_apuesta = None
        self.apuesta_pendiente = False
        self.esperando_resultado = False
        self.ultima_prediccion = None
        
        self.prediccion_pendiente = None
    
    def _normalizar_color(self, color: str) -> str:
        if color is None:
            return 'red'
        c = str(color).lower().strip()
        if c in ['red', 'rojo', '🔴', '1', 'r']:
            return 'red'
        if c in ['blue', 'azul', '🔵', '2', 'b']:
            return 'blue'
        return 'red'
    
    def _color_emoji(self, color: str) -> str:
        return "🔴" if color == 'red' else "🔵"
    
    def _color_contrario(self, color: str) -> str:
        return 'blue' if color == 'red' else 'red'
    
    def _calcular_siguiente_apuesta(self):
        if self.primer_color is None:
            return None
        
        if self.ciclo_actual == "primario":
            if self.rondas_actuales < 2:
                self.rondas_actuales += 1
                return self.primer_color
            else:
                self.ciclo_actual = "secundario"
                self.rondas_actuales = 1
                return self._color_contrario(self.primer_color)
        else:
            if self.rondas_actuales < 3:
                self.rondas_actuales += 1
                return self._color_contrario(self.primer_color)
            else:
                self.ciclo_actual = "primario"
                self.rondas_actuales = 1
                return self.primer_color
    
    def process_color(self, color: str):
        if not self.active:
            return
        
        color = self._normalizar_color(color)
        
        # ============================================
        # 1. VERIFICAR APUESTA PENDIENTE
        # ============================================
        if self.esperando_resultado and self.prediccion_pendiente is not None:
            is_win = (self.prediccion_pendiente == color)
            
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN (TENDENCIAL)", True)
                else:
                    self.on_result(f"❌ LOSS (TENDENCIAL)", False)
            
            self.esperando_resultado = False
            self.apuesta_pendiente = False
            self.prediccion_pendiente = None
        
        # ============================================
        # 2. ESPERAR EL PRIMER COLOR
        # ============================================
        if self.estado == "ESPERANDO":
            self.primer_color = color
            self.estado = "ACTIVO"
            self.ciclo_actual = "primario"
            self.rondas_actuales = 1
            
            if self.on_prediction:
                self.on_prediction(f"📊 TENDENCIAL ACTIVADO - Primer color: {self._color_emoji(color)}")
                self.on_prediction(f"📊 Ciclo: {self._color_emoji(color)}{self._color_emoji(color)}{self._color_emoji(self._color_contrario(color))}{self._color_emoji(self._color_contrario(color))}{self._color_emoji(self._color_contrario(color))} ...")
            
            self.color_apuesta = self.primer_color
            self.apuesta_pendiente = True
            self.esperando_resultado = True
            self.prediccion_pendiente = self.color_apuesta
            
            if self.on_prediction:
                self.on_prediction(f"🎯 TENDENCIAL (1/2): {self._color_emoji(self.color_apuesta)}")
            return
        
        # ============================================
        # 3. CALCULAR SIGUIENTE APUESTA
        # ============================================
        if self.estado == "ACTIVO" and not self.apuesta_pendiente:
            siguiente = self._calcular_siguiente_apuesta()
            
            if siguiente is not None:
                self.color_apuesta = siguiente
                self.apuesta_pendiente = True
                self.esperando_resultado = True
                self.prediccion_pendiente = self.color_apuesta
                
                if self.ciclo_actual == "primario":
                    emoji = self._color_emoji(self.color_apuesta)
                    self.on_prediction(f"🎯 TENDENCIAL ({self.rondas_actuales}/2): {emoji}")
                else:
                    emoji = self._color_emoji(self.color_apuesta)
                    self.on_prediction(f"🎯 TENDENCIAL ({self.rondas_actuales}/3): {emoji}")
    
    def reset(self):
        self.estado = "ESPERANDO"
        self.primer_color = None
        self.ciclo_actual = None
        self.rondas_actuales = 0
        self.color_apuesta = None
        self.apuesta_pendiente = False
        self.esperando_resultado = False
        self.prediccion_pendiente = None

# ==================== PREDICTOR PRO ====================
class ProPredictor:
    """
    ESTRATEGIA PRO CORREGIDA CON SISTEMA DE APUESTA PENDIENTE
    """
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.active = True
        self.on_prediction = None
        self.on_result = None
        
        # Estado PRO
        self.session_history = []
        self.last_prediction = None
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        
        # SISTEMA DE APUESTA PENDIENTE
        self.apuesta_pendiente = False
        self.prediccion_pendiente = None
        
        # Estado actual del modo
        self.modo_actual = "BASE"
        self.patron_color = None
        self.alternancia_activa = False
    
    def _normalizar_color(self, color: str) -> str:
        if color is None:
            return 'red'
        c = str(color).lower().strip()
        if c in ['red', 'rojo', '🔴', '1', 'r']:
            return 'red'
        if c in ['blue', 'azul', '🔵', '2', 'b']:
            return 'blue'
        return 'red'
    
    def _color_emoji(self, color: str) -> str:
        return "🔴" if color == 'red' else "🔵"
    
    def _color_contrario(self, color: str) -> str:
        return 'blue' if color == 'red' else 'red'
    
    def _check_triple(self, colores) -> bool:
        if len(colores) < 3:
            return False
        return colores[-1] == colores[-2] == colores[-3]
    
    def _check_doble(self, colores) -> bool:
        if len(colores) < 2:
            return False
        return colores[-1] == colores[-2]
    
    def _check_alternancia(self, colores) -> Optional[str]:
        if len(colores) < 3:
            return None
        
        ultimos = colores[-4:] if len(colores) >= 4 else colores[-3:]
        
        if len(ultimos) >= 3:
            if ultimos[-1] != ultimos[-2] and ultimos[-2] != ultimos[-3]:
                return ultimos[-2]
        
        if len(ultimos) >= 4:
            if (ultimos[-1] != ultimos[-2] and 
                ultimos[-2] != ultimos[-3] and 
                ultimos[-3] != ultimos[-4]):
                return ultimos[-3]
        
        return None
    
    def _detectar_patron(self, colores):
        if len(colores) < 2:
            return None, "BASE", "BASE"
        
        # PRIORIDAD 1: TRIPLE
        if self._check_triple(colores):
            color_patron = colores[-1]
            prediccion = self._color_contrario(color_patron)
            return prediccion, "TRIPLE", "TRIPLE"
        
        # PRIORIDAD 2: DOBLE
        if self._check_doble(colores):
            color_patron = colores[-1]
            prediccion = self._color_contrario(color_patron)
            return prediccion, "DOBLE", "DOBLE"
        
        # PRIORIDAD 3: ALTERNANCIA
        alternancia = self._check_alternancia(colores)
        if alternancia is not None:
            return alternancia, "ALTERNANCIA", "ALTERNANCIA"
        
        # PRIORIDAD 4: BASE
        return colores[-1], "BASE", "BASE"
    
    def process_color(self, color: str):
        if not self.active:
            return
        
        color = self._normalizar_color(color)
        
        # ============================================
        # 1. VERIFICAR APUESTA PENDIENTE
        # ============================================
        if self.apuesta_pendiente and self.prediccion_pendiente is not None:
            is_win = (self.prediccion_pendiente == color)
            
            if self.on_result:
                if is_win:
                    self.on_result(f"✅ WIN (PRO)", True)
                    self.consecutive_wins += 1
                    self.consecutive_losses = 0
                    
                    if self.modo_actual in ["DOBLE", "TRIPLE"]:
                        self.modo_actual = "BASE"
                        self.patron_color = None
                        self.session_history = []
                        if self.on_prediction:
                            self.on_prediction(f"🔄 PRO: Volviendo a BASE")
                    
                    elif self.modo_actual == "ALTERNANCIA":
                        self.alternancia_activa = True
                    
                else:
                    self.on_result(f"❌ LOSS (PRO)", False)
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0
                    
                    if self.modo_actual == "DOBLE":
                        self.modo_actual = "TRIPLE"
                        if self.on_prediction:
                            self.on_prediction(f"🔄 PRO: DOBLE falló → TRIPLE")
                    
                    elif self.modo_actual == "TRIPLE":
                        self.modo_actual = "BASE"
                        self.patron_color = None
                        self.session_history = []
                        if self.on_prediction:
                            self.on_prediction(f"🔄 PRO: TRIPLE falló → Volviendo a BASE")
                    
                    elif self.modo_actual == "ALTERNANCIA":
                        self.modo_actual = "BASE"
                        self.alternancia_activa = False
                        self.session_history = []
                        if self.on_prediction:
                            self.on_prediction(f"🔄 PRO: ALTERNANCIA rota → Volviendo a BASE")
            
            self.apuesta_pendiente = False
            self.prediccion_pendiente = None
            return
        
        # ============================================
        # 2. AGREGAR COLOR AL HISTORIAL
        # ============================================
        self.session_history.append(color)
        if len(self.session_history) > 20:
            self.session_history = self.session_history[-20:]
        
        # ============================================
        # 3. DETECTAR PATRÓN Y GENERAR PREDICCIÓN
        # ============================================
        if len(self.session_history) < 2:
            return
        
        if self.modo_actual == "ALTERNANCIA" and self.alternancia_activa:
            alternancia = self._check_alternancia(self.session_history)
            if alternancia is not None:
                prediccion = alternancia
                patron_detectado = "ALTERNANCIA"
            else:
                self.modo_actual = "BASE"
                self.alternancia_activa = False
                self.session_history = []
                if self.on_prediction:
                    self.on_prediction(f"🔄 PRO: ALTERNANCIA rota → Volviendo a BASE")
                prediccion = self.session_history[-1] if self.session_history else None
                patron_detectado = "BASE"
        else:
            prediccion, patron_detectado, nuevo_modo = self._detectar_patron(self.session_history)
            
            if nuevo_modo == "ALTERNANCIA":
                self.modo_actual = "ALTERNANCIA"
                self.alternancia_activa = True
            elif nuevo_modo in ["DOBLE", "TRIPLE"]:
                self.modo_actual = nuevo_modo
            else:
                self.modo_actual = "BASE"
        
        # ============================================
        # 4. GUARDAR PREDICCIÓN COMO PENDIENTE
        # ============================================
        if prediccion is None:
            if self.session_history:
                prediccion = self.session_history[-1]
            else:
                return
            patron_detectado = "BASE"
        
        self.prediccion_pendiente = prediccion
        self.apuesta_pendiente = True
        self.last_prediction = prediccion
        
        emoji = self._color_emoji(prediccion)
        
        if self.on_prediction:
            if patron_detectado == "TRIPLE":
                color_patron = self.session_history[-1] if self.session_history else 'red'
                self.on_prediction(f"🎯 PRO (TRIPLE {self._color_emoji(color_patron)}{self._color_emoji(color_patron)}{self._color_emoji(color_patron)} → {emoji})")
            elif patron_detectado == "DOBLE":
                color_patron = self.session_history[-1] if self.session_history else 'red'
                self.on_prediction(f"🎯 PRO (DOBLE {self._color_emoji(color_patron)}{self._color_emoji(color_patron)} → {emoji})")
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
    
    def register_user(self, user_id: int, mode: str, on_prediction=None, on_result=None):
        with self._lock:
            if mode == "peakbreak":
                predictor = PeakBreakPredictorV2(user_id)
            elif mode == "cazador":
                predictor = CazadorPredictor(user_id)
            elif mode == "tendencial":
                predictor = TendencialPredictor(user_id)
            elif mode == "pro":
                predictor = ProPredictor(user_id)
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
    
    async def _send_take_profit_image(self, user_id: int):
        try:
            await self.application.bot.send_photo(chat_id=user_id, photo=TAKE_PROFIT_IMAGE_URL, caption="🎯 TAKE PROFIT ALCANZADO")
        except:
            await self._send_message(user_id, "🎯 TAKE PROFIT ALCANZADO")
    
    def _sync_send_take_profit_image(self, user_id: int):
        asyncio.run_coroutine_threadsafe(self._send_take_profit_image(user_id), self.loop)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        license_check = self.license_manager.check_license(user_id)
        
        if not license_check['valid']:
            keyboard = [
                [InlineKeyboardButton("🔧 Hack 30d - 15 USDT", callback_data='plan_hack')],
                [InlineKeyboardButton("⛰️ Peak Break 60d - 35 USDT", callback_data='plan_peakbreak')],
                [InlineKeyboardButton("🎯 Cazador 90d - 50 USDT", callback_data='plan_cazador')],
                [InlineKeyboardButton("📊 Tendencial 75d - 45 USDT", callback_data='plan_tendencial')],
                [InlineKeyboardButton("🏆 PRO 90d - 60 USDT", callback_data='plan_pro')],
            ]
            await update.message.reply_text(
                "🔒 ACCESO RESTRINGIDO\n\nNo tienes licencia activa.\n\n"
                "💰 PLANES DISPONIBLES:\n"
                "• 🔧 Hack 30d: 15 USDT (1 cuenta) - Estrategia #3 Anti-sistema\n"
                "• ⛰️ Peak Break 60d: 35 USDT (1 cuenta) - Hereda HACK, WIN + N LOSS\n"
                "• 🎯 Cazador 90d: 50 USDT (1 cuenta) - Patrones DOBLE y TRIPLE con BLOQUEO\n"
                "• 📊 Tendencial 75d: 45 USDT (1 cuenta) - Ciclo fijo 2-3-2-3\n"
                "• 🏆 PRO 90d: 60 USDT (1 cuenta) - BASE + DOBLE/TRIPLE + ALTERNANCIA\n\n"
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
        elif mode == "peakbreak":
            modo_texto = "⛰️ PEAK BREAK V2 (WIN + N LOSS, N=1/2 cíclico)"
        elif mode == "cazador":
            modo_texto = "🎯 CAZADOR (Patrones DOBLE y TRIPLE con BLOQUEO)"
        elif mode == "tendencial":
            modo_texto = "📊 TENDENCIAL (Ciclo fijo 2-3-2-3)"
        else:
            modo_texto = "🏆 PRO (BASE + DOBLE/TRIPLE + ALTERNANCIA) - CON APUESTA PENDIENTE"
        
        keyboard = [
            [InlineKeyboardButton("📡 MODO SEÑALES", callback_data='signals_mode')],
            [InlineKeyboardButton("🤖 MODO AUTOMATICO", callback_data='auto_mode')],
            [InlineKeyboardButton("📜 Info Licencia", callback_data='license_info')],
            [InlineKeyboardButton("💰 Comprar Licencia", callback_data='buy_license')]
        ]
        
        await update.message.reply_text(
            f"🎰 PREDICTOR BOT V7\n\n"
            f"✅ Licencia: {plan_name}\n"
            f"🎲 Modo: {modo_texto}\n"
            f"👥 Máx cuentas: {max_accounts}\n\n"
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
        
        if mode == "hack":
            desc = "• Sigue el último color que sale\n• Si falla 2 veces seguidas → activa MODO ANTI por 2 rondas\n• En modo ANTI, apuesta al color contrario"
        elif mode == "peakbreak":
            desc = "• Hereda la lógica HACK\n• Detecta WIN real comparando predicción con resultado\n• Se activa con WIN + N LOSS (N=1 o 2, cíclico)\n• Sigue apostando mientras ganes\n• Al primer LOSS, espera el patrón de activación"
        elif mode == "cazador":
            desc = "• Busca patrones DOBLE (🔴🔴 o 🔵🔵) y TRIPLE (🔴🔴🔴 o 🔵🔵🔵)\n• Apuesta al color contrario\n• Si falla DOBLE → automáticamente TRIPLE\n• Al WIN o LOSS en TRIPLE → BLOQUEA el color del patrón\n• No detecta el color bloqueado hasta que aparezca el contrario\n• Espera el primer cambio de color para activarse"
        elif mode == "tendencial":
            desc = "• Espera el PRIMER COLOR que sale\n• Ciclo fijo: 2 del primer color, 3 del contrario, 2, 3, 2, 3...\n• NO cambia por WIN/LOSS, sigue el ciclo fijo\n• PERO muestra el resultado de cada apuesta (WIN/LOSS)"
        else:
            desc = "• Siempre comienza en BASE (seguir color)\n• DOBLE: apuesta CONTRARIO, si WIN → BASE, si LOSS → TRIPLE\n• TRIPLE: apuesta CONTRARIO, SIEMPRE vuelve a BASE (WIN o LOSS)\n• ALTERNANCIA: se mantiene hasta que rompa, luego BASE\n• PRIORIDAD: TRIPLE > DOBLE > ALTERNANCIA > BASE\n• CON SISTEMA DE APUESTA PENDIENTE para evitar errores"
        
        await query.edit_message_text(
            f"📡 MODO SEÑALES ACTIVADO - {mode.upper()}\n\n"
            f"🎯 Reglas:\n{desc}\n\n"
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
        
        if mode == "hack":
            desc = "• Sigue el último color que sale\n• Si falla 2 veces seguidas → activa MODO ANTI por 2 rondas"
        elif mode == "peakbreak":
            desc = "• Hereda la lógica HACK\n• Detecta WIN real comparando predicción con resultado\n• Se activa con WIN + N LOSS (N=1 o 2, cíclico)\n• Sigue apostando mientras ganes\n• Al primer LOSS, espera el patrón de activación"
        elif mode == "cazador":
            desc = "• Busca patrones DOBLE (🔴🔴 o 🔵🔵) y TRIPLE (🔴🔴🔴 o 🔵🔵🔵)\n• Apuesta al color contrario\n• Si falla DOBLE → automáticamente TRIPLE\n• Al WIN o LOSS en TRIPLE → BLOQUEA el color del patrón\n• No detecta el color bloqueado hasta que aparezca el contrario\n• Espera el primer cambio de color para activarse"
        elif mode == "tendencial":
            desc = "• Espera el PRIMER COLOR que sale\n• Ciclo fijo: 2 del primer color, 3 del contrario, 2, 3, 2, 3...\n• NO cambia por WIN/LOSS, sigue el ciclo fijo\n• PERO muestra el resultado de cada apuesta (WIN/LOSS)"
        else:
            desc = "• Siempre comienza en BASE (seguir color)\n• DOBLE: apuesta CONTRARIO, si WIN → BASE, si LOSS → TRIPLE\n• TRIPLE: apuesta CONTRARIO, SIEMPRE vuelve a BASE (WIN o LOSS)\n• ALTERNANCIA: se mantiene hasta que rompa, luego BASE\n• PRIORIDAD: TRIPLE > DOBLE > ALTERNANCIA > BASE\n• CON SISTEMA DE APUESTA PENDIENTE para evitar errores"
        
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
                    'restart_bet': 0.1,
                    'max_pauses': 2,
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
            # ⭐ CRÍTICO: Si está en pausa, NO apostar
            if account.paused:
                continue
            
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
            # ⭐ CRÍTICO: Si está en pausa y hay WIN → REACTIVAR
            if account.paused and won:
                account.reactivate_from_pause()
                self._sync_send_message(user_id, f"✅ WIN DETECTADO - ¡CUENTA REACTIVADA!")
                self._sync_send_message(user_id, f"🔄 Reiniciando apuestas a: ${account.restart_bet:.2f}")
                self._sync_send_message(user_id, f"💰 {account.username}: Apuesta reiniciada")
                self._sync_send_message(user_id, f"📊 Contador de pérdidas: 0/{account.max_consecutive_losses}")
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
                        self._sync_send_message(user_id, f"💰 Saldo inicial: ${account.saldo_inicial_pausa:.2f}")
                        self._sync_send_message(user_id, f"💰 Saldo actual: ${account.balance:.2f}")
                        self._sync_send_message(user_id, f"💰 Ganancia recuperada: ${account.saldo_perdido:.2f}")
                        self._sync_send_message(user_id, f"🔄 Volviendo a apuesta inicial original: ${account.initial_bet_original:.2f}")
                        self._sync_send_message(user_id, f"📊 Pausas usadas: {account.current_pauses}/{account.max_pauses}")
                        account.saldo_perdido = 0
                        account.saldo_inicial_pausa = 0
                
                self._sync_send_message(user_id, f"💰 {account.username}: WIN - Reiniciada a ${account.current_bet:.2f}")
                
                if account.check_take_profit():
                    account.betting_active = False
                    profit_info = account.get_profit_info()
                    self._sync_send_message(user_id, f"🎯 ¡TAKE PROFIT ALCANZADO! {account.username}\n{profit_info}\n🛑 Apuestas detenidas para esta cuenta")
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
                        self._sync_send_message(user_id, f"💰 Saldo actual: ${account.balance:.2f}")
                        self._sync_send_message(user_id, f"💰 Saldo perdido: ${account.saldo_perdido:.2f}")
                        self._sync_send_message(user_id, f"💤 Cuenta en PAUSA #{account.current_pauses}/{account.max_pauses} - Esperando WIN para reiniciar")
                        self._sync_send_message(user_id, f"🔄 Monto de reinicio: ${account.restart_bet:.2f}")
                        account.betting_active = False
                    else:
                        self._sync_send_message(user_id, f"❌ {account.username}: No se pudo activar pausa")
                        
                elif stop_loss_status == "DETENER":
                    account.betting_active = False
                    self._sync_send_message(user_id, f"🛑 LÍMITE DE PAUSAS ALCANZADO - {account.username}")
                    self._sync_send_message(user_id, f"📊 Pausas usadas: {account.current_pauses}/{account.max_pauses}")
                    self._sync_send_message(user_id, f"💤 Cuenta DETENIDA PERMANENTEMENTE")
                    self._sync_send_message(user_id, f"💰 Saldo actual: ${account.balance:.2f}")
                    if account.saldo_recuperado:
                        self._sync_send_message(user_id, f"✅ Saldo recuperado: Sí")
                    else:
                        self._sync_send_message(user_id, f"❌ Saldo recuperado: No (pendiente ${account.saldo_perdido:.2f})")
                    self._sync_send_message(user_id, f"🔄 Usa /start para reiniciar manualmente")
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
    
    async def show_betting_config(self, update, user_id):
        session = self.user_sessions[user_id]
        config = session['bet_config']
        bot_mode = session.get('bot_mode', 'hack')
        
        take_profit_val = config.get('take_profit', 0)
        if take_profit_val == 0:
            tp_display = "DESACTIVADO"
        else:
            tp_display = f"${take_profit_val}"
        
        if bot_mode == "hack":
            modo_texto = "HACK (Anti-sistema)"
        elif bot_mode == "peakbreak":
            modo_texto = "PEAK BREAK V2 (WIN + N LOSS)"
        elif bot_mode == "cazador":
            modo_texto = "CAZADOR (Doble/Triple con BLOQUEO)"
        elif bot_mode == "tendencial":
            modo_texto = "TENDENCIAL (Ciclo 2-3-2-3)"
        else:
            modo_texto = "PRO (BASE + DOBLE/TRIPLE + ALTERNANCIA)"
        
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
        
        msg = (f"⚙️ CONFIGURACIÓN - {modo_texto}\n\n"
               f"💰 Apuesta actual: ${config['current_bet']}\n"
               f"🎲 Modo gestión: {'Martingala (x2)' if config['use_martingale'] else 'Agresivo (x2+inicial)'}\n"
               f"🛑 Stop Loss: {config['max_losses']} pérdidas consecutivas\n"
               f"🔄 Reinicio: ${config.get('restart_bet', 0.1)} (después de pausa)\n"
               f"⏸️ Max Pausas: {config.get('max_pauses', 2)}\n"
               f"🎯 Take Profit: {tp_display}\n\n"
               f"📌 Cuando alcanza el Stop Loss → PAUSA\n"
               f"📌 Espera un WIN para reiniciar\n"
               f"📌 Recupera el saldo perdido\n"
               f"📌 Vuelve a la apuesta inicial original\n"
               f"📌 Después de {config.get('max_pauses', 2)} pausas → DETENCIÓN PERMANENTE")
        
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
        await update.callback_query.edit_message_text(
            "💰 Envía nuevo monto inicial (mínimo 0.1):\n\n"
            "Este será el monto base para las apuestas."
        )
        context.user_data['awaiting_initial_bet'] = True
    
    async def cfg_restart_bet(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "🔄 Envía el monto de REINICIO (mínimo 0.1):\n\n"
            "Este será el monto con el que reiniciará después de una pausa."
        )
        context.user_data['awaiting_restart_bet'] = True
    
    async def cfg_max_pauses(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "⏸️ Envía el número máximo de pausas permitidas (1-5):\n\n"
            "Después de este número, la cuenta se detendrá permanentemente."
        )
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
            reglas = "• Sigue el último color que sale\n• Si falla 2 veces seguidas → activa MODO ANTI por 2 rondas"
        elif bot_mode == "peakbreak":
            reglas = "• Hereda la lógica HACK\n• Detecta WIN real comparando predicción con resultado\n• Se activa con WIN + N LOSS (N=1 o 2, cíclico)\n• Sigue apostando mientras ganes\n• Al primer LOSS, espera el patrón de activación"
        elif bot_mode == "cazador":
            reglas = "• Busca patrones DOBLE (🔴🔴 o 🔵🔵) y TRIPLE (🔴🔴🔴 o 🔵🔵🔵)\n• Apuesta al color contrario\n• Si falla DOBLE → automáticamente TRIPLE\n• Al WIN o LOSS en TRIPLE → BLOQUEA el color del patrón\n• No detecta el color bloqueado hasta que aparezca el contrario\n• Espera el primer cambio de color para activarse"
        elif bot_mode == "tendencial":
            reglas = "• Espera el PRIMER COLOR que sale\n• Ciclo fijo: 2 del primer color, 3 del contrario, 2, 3, 2, 3...\n• NO cambia por WIN/LOSS, sigue el ciclo fijo\n• PERO muestra el resultado de cada apuesta (WIN/LOSS)"
        else:
            reglas = "• Siempre comienza en BASE (seguir color)\n• DOBLE: apuesta CONTRARIO, si WIN → BASE, si LOSS → TRIPLE\n• TRIPLE: apuesta CONTRARIO, SIEMPRE vuelve a BASE (WIN o LOSS)\n• ALTERNANCIA: se mantiene hasta que rompa, luego BASE\n• PRIORIDAD: TRIPLE > DOBLE > ALTERNANCIA > BASE\n• CON SISTEMA DE APUESTA PENDIENTE"
        
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
            f"📌 Cuando alcanza Stop Loss → PAUSA\n"
            f"📌 Espera WIN para reiniciar\n"
            f"📌 Recupera el saldo perdido\n"
            f"📌 Vuelve a la apuesta original\n"
            f"📌 Después de {max_pauses} pausas → DETENCIÓN PERMANENTE\n\n"
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
    
    async def buy_license(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🔧 Hack 30d - 15 USDT", callback_data='plan_hack')],
            [InlineKeyboardButton("⛰️ Peak Break 60d - 35 USDT", callback_data='plan_peakbreak')],
            [InlineKeyboardButton("🎯 Cazador 90d - 50 USDT", callback_data='plan_cazador')],
            [InlineKeyboardButton("📊 Tendencial 75d - 45 USDT", callback_data='plan_tendencial')],
            [InlineKeyboardButton("🏆 PRO 90d - 60 USDT", callback_data='plan_pro')],
        ]
        await update.callback_query.edit_message_text(
            "💰 COMPRAR LICENCIA\n\n"
            "Selecciona un plan:",
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
            
            if mode == "hack":
                desc = "HACK (Anti-sistema): Sigue el último color + ANTI tras 2 pérdidas"
            elif mode == "peakbreak":
                desc = "PEAK BREAK V2: Hereda HACK, WIN + N LOSS (N=1/2 cíclico)"
            elif mode == "cazador":
                desc = "CAZADOR: Patrones DOBLE y TRIPLE con BLOQUEO de color"
            elif mode == "tendencial":
                desc = "TENDENCIAL: Ciclo fijo 2-3-2-3 basado en el primer color"
            else:
                desc = "PRO: BASE + DOBLE/TRIPLE (CONTRARIO) + ALTERNANCIA - CON APUESTA PENDIENTE"
            
            await query.edit_message_text(
                f"📜 INFORMACIÓN DE LICENCIA\n\n"
                f"📋 Plan: {LICENSE_PLANS[data['plan']]['name']}\n"
                f"🎲 Estrategia: {desc}\n"
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
                "• hack - Hack 30 días (15 USDT) - Estrategia Anti-sistema\n"
                "• peakbreak - Peak Break 60 días (35 USDT) - WIN + N LOSS\n"
                "• cazador - Cazador 90 días (50 USDT) - Patrones DOBLE y TRIPLE con BLOQUEO\n"
                "• tendencial - Tendencial 75 días (45 USDT) - Ciclo fijo 2-3-2-3\n"
                "• pro - PRO 90 días (60 USDT) - BASE + DOBLE/TRIPLE + ALTERNANCIA (CON APUESTA PENDIENTE)\n\n"
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
                
                if plan == "hack":
                    mode_desc = "HACK (Anti-sistema: seguir color + ANTI tras 2 pérdidas)"
                elif plan == "peakbreak":
                    mode_desc = "PEAK BREAK V2 (Hereda HACK, WIN + N LOSS, N=1/2 cíclico)"
                elif plan == "cazador":
                    mode_desc = "CAZADOR (Patrones DOBLE y TRIPLE con BLOQUEO de color)"
                elif plan == "tendencial":
                    mode_desc = "TENDENCIAL (Ciclo fijo 2-3-2-3 basado en el primer color)"
                else:
                    mode_desc = "PRO (BASE + DOBLE/TRIPLE CONTRARIO + ALTERNANCIA) - CON APUESTA PENDIENTE"
                
                await self._send_message(
                    target_user_id,
                    f"🎉 ¡LICENCIA ACTIVADA!\n\n"
                    f"📦 Plan: {plan_name}\n"
                    f"👥 Máx cuentas: {LICENSE_PLANS[plan]['max_users']}\n"
                    f"🎲 Estrategia: {mode_desc}\n\n"
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
        
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_messages))
        self.application.add_handler(MessageHandler(filters.PHOTO, self.handle_any_photo))
        
        print("=" * 70)
        print("🎰 PREDICTOR BOT V7 - DEFINITIVO")
        print("=" * 70)
        print("💰 PLANES DE LICENCIA:")
        print("  • 🔧 Hack 30d: 15 USDT (1 cuenta) - Estrategia #3 Anti-sistema")
        print("  • ⛰️ Peak Break 60d: 35 USDT (1 cuenta) - WIN + N LOSS (N=1/2 cíclico)")
        print("  • 🎯 Cazador 90d: 50 USDT (1 cuenta) - Patrones DOBLE y TRIPLE con BLOQUEO")
        print("  • 📊 Tendencial 75d: 45 USDT (1 cuenta) - Ciclo fijo 2-3-2-3")
        print("  • 🏆 PRO 90d: 60 USDT (1 cuenta) - BASE + DOBLE/TRIPLE + ALTERNANCIA")
        print("=" * 70)
        print("🔄 SISTEMA DE PAUSA Y REINICIO:")
        print("  • Cuando alcanza Stop Loss → PAUSA (espera WIN)")
        print("  • Al detectar WIN → REINICIA con monto configurado")
        print("  • RECUPERA el saldo perdido")
        print("  • Vuelve a la APUESTA INICIAL ORIGINAL")
        print("  • Notifica cuando el saldo se recupera")
        print("  • Máximo de pausas configurable (1-5)")
        print("  • Al llegar al límite → DETENCIÓN PERMANENTE")
        print("=" * 70)
        print("🏆 MODO PRO:")
        print("  • Siempre comienza en BASE (seguir color)")
        print("  • DOBLE: apuesta CONTRARIO, si WIN → BASE, si LOSS → TRIPLE")
        print("  • TRIPLE: apuesta CONTRARIO, SIEMPRE vuelve a BASE (WIN o LOSS)")
        print("  • ALTERNANCIA: se mantiene hasta que rompa, luego BASE")
        print("  • PRIORIDAD: TRIPLE > DOBLE > ALTERNANCIA > BASE")
        print("=" * 70)
        print("✅ SISTEMA DE APUESTA PENDIENTE IMPLEMENTADO EN TODOS LOS MODOS")
        print("   → Elimina errores intermitentes de WIN/LOSS")
        print("=" * 70)
        print("✅ BOT LISTO")
        print("=" * 70)
        
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    print("🚀 INICIANDO PREDICTOR BOT V7 (DEFINITIVO)...")
    bot = PredictionBot(BOT_TOKEN)
    bot.run()