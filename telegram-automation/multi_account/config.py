"""
Multi-Account Telegram Broadcaster
Конфигурация и утилиты
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# BASE_DIR — корень проекта (родительская папка для multi_account/)
BASE_DIR = Path(__file__).parent.parent.resolve()
ACCOUNTS_PATH = BASE_DIR / 'accounts.json'
TEMPLATES_PATH = BASE_DIR / 'config' / 'templates.json'
CHATS_PATH = BASE_DIR / 'config' / 'chats.json'
SESSIONS_DIR = BASE_DIR / 'sessions'


class Config:
    """Глобальная конфигурация"""
    
    @staticmethod
    def load_accounts() -> Dict:
        """Загрузить конфигурацию аккаунтов"""
        if not ACCOUNTS_PATH.exists():
            return {
                'settings': {
                    'auto_distribute_chats': True,
                    'min_delay_between_messages': 50,
                    'max_delay_between_messages': 100,
                    'daily_limit_per_account': 500
                },
                'accounts': []
            }
        
        with open(ACCOUNTS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def save_accounts(data: Dict):
        """Сохранить конфигурацию аккаунтов"""
        with open(ACCOUNTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def get_enabled_accounts() -> List[Dict]:
        """Получить список включённых аккаунтов"""
        data = Config.load_accounts()
        return [a for a in data.get('accounts', []) if a.get('enabled', True)]
    
    @staticmethod
    def get_account_by_id(account_id: int) -> Optional[Dict]:
        """Получить аккаунт по ID"""
        data = Config.load_accounts()
        for acc in data.get('accounts', []):
            if acc.get('id') == account_id:
                return acc
        return None
    
    @staticmethod
    def get_templates() -> Dict:
        """Загрузить шаблоны"""
        if not TEMPLATES_PATH.exists():
            return {}
        with open(TEMPLATES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def get_chats() -> List[Dict]:
        """Загрузить чаты"""
        if not CHATS_PATH.exists():
            return []
        with open(CHATS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        chats = data.get('chats', [])
        return [c for c in chats if c.get('enabled', True)]
    
    @staticmethod
    def get_default_photo_path() -> Optional[str]:
        """Получить путь к фото по умолчанию"""
        templates = Config.get_templates()
        return templates.get('default_photo')
    
    @staticmethod
    def get_global_settings() -> Dict:
        """Получить глобальные настройки"""
        data = Config.load_accounts()
        return data.get('settings', {})


class AccountConfig:
    """Конфигурация отдельного аккаунта"""
    
    def __init__(self, account_data: Dict):
        self.data = account_data
        self.id = account_data.get('id')
        self.name = account_data.get('name', f'Аккаунт {self.id}')
        self.enabled = account_data.get('enabled', True)
        self.session_name = account_data.get('session_name', f'account_{self.id}')
        self.api_id = int(account_data.get('api_id', 0))
        self.api_hash = account_data.get('api_hash', '')
        self.phone = account_data.get('phone', '')
    
    @property
    def session_path(self) -> Path:
        """Путь к сессии"""
        return SESSIONS_DIR / self.session_name
    
    @property
    def script_config(self) -> Dict:
        """Конфигурация скрипта"""
        return self.data.get('script', {
            'enabled': False,
            'template_id': None,
            'custom_text': None
        })
    
    @property
    def photo_config(self) -> Dict:
        """Конфигурация фото"""
        return self.data.get('photo', {
            'enabled': True,
            'use_default': True,
            'custom_path': None
        })
    
    @property
    def limits(self) -> Dict:
        """Лимиты аккаунта"""
        acc_limits = self.data.get('limits', {})
        
        if acc_limits.get('use_global', True):
            global_settings = Config.get_global_settings()
            return {
                'daily_limit': global_settings.get('daily_limit_per_account', 500),
                'min_delay': global_settings.get('min_delay_between_messages', 50),
                'max_delay': global_settings.get('max_delay_between_messages', 100)
            }
        
        return {
            'daily_limit': acc_limits.get('daily_limit', 500),
            'min_delay': acc_limits.get('min_delay', 50),
            'max_delay': acc_limits.get('max_delay', 100)
        }
    
    def get_text(self) -> Optional[str]:
        """Получить текст для рассылки"""
        script = self.script_config
        
        if script.get('enabled', False):
            # Кастомный текст
            if script.get('custom_text'):
                return script['custom_text']
            
            # Текст из шаблона
            template_id = script.get('template_id')
            if template_id:
                templates = Config.get_templates()
                for t in templates.get('templates', []):
                    if t.get('id') == template_id:
                        return t.get('text')
        
        return None
    
    def get_photo_path(self) -> Optional[Path]:
        """Получить путь к фото"""
        photo = self.photo_config
        
        if not photo.get('enabled', True):
            return None
        
        if photo.get('custom_path'):
            p = Path(photo['custom_path'])
            if p.exists():
                return p
        
        if photo.get('use_default', True):
            default_path = Config.get_default_photo_path()
            if default_path:
                p = Path(default_path)
                if p.exists():
                    return p
        
        return None
    
    def is_ready(self) -> bool:
        """Готов ли аккаунт к работе"""
        return bool(
            self.enabled and
            self.api_id and
            self.api_hash and
            self.phone
        )
    
    def __repr__(self):
        return f"AccountConfig(id={self.id}, name='{self.name}', ready={self.is_ready()})"
