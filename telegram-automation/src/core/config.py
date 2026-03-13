"""
Configuration loader and validator
"""

import json
import os
from pathlib import Path
from typing import Any, Dict


class Config:
    """Configuration manager with validation"""
    
    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = {}
        self._load()
        self._validate()
    
    def _load(self) -> None:
        """Load configuration from JSON file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = json.load(f)
    
    def _validate(self) -> None:
        """Validate required configuration fields"""
        required_fields = [
            'telegram.api_id',
            'telegram.api_hash',
            'telegram.phone',
            'message_limits.daily_limit',
            'delays.min_delay_seconds',
            'delays.max_delay_seconds'
        ]
        
        for field in required_fields:
            value = self._get_nested(field)
            if value is None or value == "":
                raise ValueError(f"Missing required config field: {field}")
            
            # Validate API credentials
            if field == 'telegram.api_id' and not isinstance(value, int):
                raise TypeError(f"api_id must be integer, got {type(value)}")
    
    def _get_nested(self, path: str) -> Any:
        """Get nested value from config using dot notation"""
        keys = path.split('.')
        value = self._config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value
    
    def get(self, path: str, default: Any = None) -> Any:
        """Get configuration value with optional default"""
        value = self._get_nested(path)
        return value if value is not None else default
    
    @property
    def telegram(self) -> Dict[str, Any]:
        """Get telegram settings"""
        return self._config.get('telegram', {})
    
    @property
    def message_limits(self) -> Dict[str, Any]:
        """Get message limits settings"""
        return self._config.get('message_limits', {})
    
    @property
    def delays(self) -> Dict[str, Any]:
        """Get delay settings"""
        return self._config.get('delays', {})
    
    @property
    def auto_reply(self) -> Dict[str, Any]:
        """Get auto-reply settings"""
        return self._config.get('auto_reply', {})
    
    @property
    def logging(self) -> Dict[str, Any]:
        """Get logging settings"""
        return self._config.get('logging', {})
    
    @property
    def database(self) -> Dict[str, Any]:
        """Get database settings"""
        return self._config.get('database', {})
    
    @property
    def session(self) -> Dict[str, Any]:
        """Get session settings"""
        return self._config.get('session', {})
    
    @property
    def proxy(self) -> Dict[str, Any]:
        """Get proxy settings"""
        return self._config.get('proxy', {})
