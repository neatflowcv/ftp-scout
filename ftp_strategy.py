from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from robust_ftp import RobustFTPConnection


class FTPDirectoryStrategy(ABC):
    """FTP 디렉토리 내용 가져오기 전략의 추상 기본 클래스"""
    
    @abstractmethod
    def get_directory_contents(self, ftp_conn: RobustFTPConnection) -> Optional[List[Tuple[str, bool]]]:
        """
        디렉토리 내용을 가져오는 추상 메서드
        
        Args:
            ftp_conn: FTP 연결 객체
            
        Returns:
            List[Tuple[str, bool]]: (파일명, is_directory) 튜플의 리스트 또는 None (실패시)
        """
        pass
    
    @abstractmethod
    def get_strategy_name(self) -> str:
        """전략 이름을 반환하는 추상 메서드"""
        pass


class FTPDirectoryContext:
    """FTP 디렉토리 내용 가져오기 전략을 관리하는 Context 클래스"""
    
    def __init__(self):
        self._strategies: List[FTPDirectoryStrategy] = []
        self._current_strategy: Optional[FTPDirectoryStrategy] = None
    
    def add_strategy(self, strategy: FTPDirectoryStrategy) -> None:
        """전략을 추가합니다."""
        self._strategies.append(strategy)
    
    def set_strategy(self, strategy: FTPDirectoryStrategy) -> None:
        """현재 사용할 전략을 설정합니다."""
        self._current_strategy = strategy
    
    def auto_select_strategy(self, ftp_conn: RobustFTPConnection) -> Optional[FTPDirectoryStrategy]:
        """
        사용 가능한 전략을 자동으로 선택합니다.
        우선순위에 따라 각 전략을 테스트하고 첫 번째로 성공하는 전략을 선택합니다.
        """
        for strategy in self._strategies:
            try:
                result = strategy.get_directory_contents(ftp_conn)
                if result is not None:
                    self._current_strategy = strategy
                    print(f"{strategy.get_strategy_name()} 전략이 선택되었습니다.")
                    return strategy
            except Exception as e:
                print(f"{strategy.get_strategy_name()} 전략 테스트 실패: {e}")
                continue
        
        print("사용 가능한 전략이 없습니다.")
        return None
    
    def execute_strategy(self, ftp_conn: RobustFTPConnection) -> Optional[List[Tuple[str, bool]]]:
        """현재 설정된 전략을 실행합니다."""
        if self._current_strategy is None:
            raise ValueError("전략이 설정되지 않았습니다. auto_select_strategy() 또는 set_strategy()를 먼저 호출하세요.")
        
        return self._current_strategy.get_directory_contents(ftp_conn)
    
    def get_current_strategy_name(self) -> str:
        """현재 전략의 이름을 반환합니다."""
        if self._current_strategy is None:
            return "전략이 설정되지 않음"
        return self._current_strategy.get_strategy_name()
    
    def get_available_strategies(self) -> List[str]:
        """사용 가능한 모든 전략의 이름을 반환합니다."""
        return [strategy.get_strategy_name() for strategy in self._strategies] 