"""
数据存储基类
"""
import json
from pathlib import Path
from typing import Dict, Any, List
from threading import Lock

class BaseModel:
    """数据存储基类"""
    
    _lock = Lock()
    _instances = {}
    
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.data_dir / 'metadata.json'
        self._data = None
        
    def _load(self) -> Dict[str, Any]:
        """加载数据"""
        with self._lock:
            if self._data is None:
                if self.metadata_file.exists():
                    with open(self.metadata_file, 'r', encoding='utf-8') as f:
                        self._data = json.load(f)
                else:
                    self._data = self._get_default_data()
                    self._save()
            return self._data
    
    def _save(self):
        """保存数据"""
        with self._lock:
            if self._data is not None:
                with open(self.metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=2)
    
    def _get_default_data(self) -> Dict[str, Any]:
        """获取默认数据结构"""
        raise NotImplementedError("子类必须实现_get_default_data方法")
    
    def reload(self):
        """重新加载数据"""
        self._data = None
        return self._load()
