import socket
from ftplib import FTP, error_temp
from collections import deque
import os
import time
import argparse
from typing import Generator, Optional


class RobustFTPConnection:
    """재연결 기능이 있는 견고한 FTP 연결 클래스"""
    
    # 클래스 필드 타입 선언
    host: str
    username: str
    password: str
    ftp: Optional[FTP]

    def __init__(self, host: str, username: str, password: str) -> None:
        """
        FTP 연결 객체를 초기화합니다.
        
        Args:
            host: FTP 서버 호스트 주소
            username: FTP 사용자명
            password: FTP 비밀번호
        """
        self.host = host
        self.username = username
        self.password = password
        self.ftp: Optional[FTP] = None
        self.connect()

    def connect(self, max_retries: int = 3) -> None:
        """FTP 서버에 연결합니다."""
        for attempt in range(max_retries + 1):
            try:
                if self.ftp:
                    try:
                        self.ftp.quit()
                    except Exception:
                        pass

                self.ftp = FTP(self.host, timeout=30)
                self.ftp.login(user=self.username, passwd=self.password)
                print(f"Connected to FTP server: {self.host} (attempt {attempt + 1})")
                return
            except (ConnectionError, socket.timeout, socket.error, error_temp) as e:
                print(f"FTP 연결 실패 (시도 {attempt + 1}/{max_retries + 1}): {e}")
                if attempt == max_retries:
                    raise
                time.sleep(2**attempt)  # 지수적 백오프
            except Exception as e:
                print(f"FTP 연결 중 오류 발생: {e}")
                raise

    def is_connected(self) -> bool:
        """FTP 연결이 살아있는지 확인합니다."""
        try:
            if not self.ftp:
                return False
            self.ftp.pwd()
            return True
        except Exception:
            return False

    def ensure_connected(self) -> None:
        """연결이 끊어졌다면 재연결합니다."""
        if not self.is_connected():
            print("FTP 연결이 끊어졌습니다. 재연결을 시도합니다...")
            self.connect()
            print("FTP 재연결 성공")

    def execute_with_retry(self, func, *args, max_retries: int = 3, **kwargs):
        """FTP 명령을 재시도 로직과 함께 실행합니다."""
        for retry in range(max_retries):
            try:
                self.ensure_connected()
                return func(*args, **kwargs)
            except (ConnectionError, socket.timeout, socket.error, error_temp) as e:
                print(f"FTP 명령 실패 (시도 {retry + 1}): {e}")
                if retry == max_retries - 1:
                    raise
                time.sleep(1)
            except Exception as e:
                print(f"FTP 명령 중 예상치 못한 오류: {e}")
                raise

    def cwd(self, path: str) -> None:
        """디렉토리 변경 (재시도 포함)"""
        return self.execute_with_retry(self.ftp.cwd, path)

    def mlsd(self, *args, **kwargs):
        """MLSD 명령 (재시도 포함)"""
        return self.execute_with_retry(self.ftp.mlsd, *args, **kwargs)

    def dir(self, callback) -> None:
        """DIR 명령 (재시도 포함)"""
        return self.execute_with_retry(self.ftp.dir, callback)

    def nlst(self, *args, **kwargs):
        """NLST 명령 (재시도 포함)"""
        return self.execute_with_retry(self.ftp.nlst, *args, **kwargs)

    def close(self) -> None:
        """FTP 연결을 종료합니다."""
        if self.ftp:
            try:
                self.ftp.quit()
                print("FTP connection closed.")
            except Exception as e:
                print(f"FTP 연결 종료 중 오류: {e}")
            finally:
                self.ftp = None


def get_directory_contents_mlsd(
    ftp_conn: RobustFTPConnection,
) -> list[tuple[str, bool]]:
    """
    MLSD 명령어를 사용하여 디렉토리 내용을 가져옵니다.

    Returns:
        list[tuple[str, bool]]: (파일명, is_directory) 튜플의 리스트
    """
    try:
        contents = []
        for name, facts in ftp_conn.mlsd():
            if name in (".", ".."):
                continue
            is_dir = facts.get("type", "").lower() == "dir"
            contents.append((name, is_dir))
        return contents
    except Exception as e:
        print(f"MLSD 실패: {e}, DIR 방식으로 대체합니다.")
        return None


def get_directory_contents_dir(ftp_conn: RobustFTPConnection) -> list[tuple[str, bool]]:
    """
    DIR (LIST) 명령어를 사용하여 디렉토리 내용을 가져옵니다.

    Returns:
        list[tuple[str, bool]]: (파일명, is_directory) 튜플의 리스트
    """
    try:
        contents = []
        dir_lines = []

        def collect_lines(line):
            dir_lines.append(line)

        ftp_conn.dir(collect_lines)

        for line in dir_lines:
            # Unix 스타일 ls -l 출력을 파싱
            # 첫 번째 문자가 'd'이면 디렉토리
            if line:
                parts = line.split()
                if len(parts) >= 9:
                    permissions = parts[0]
                    is_dir = permissions.startswith("d")
                    # 파일명은 마지막 부분 (공백이 포함될 수 있음)
                    filename = " ".join(parts[8:])
                    if filename not in (".", ".."):
                        contents.append((filename, is_dir))

        return contents
    except Exception as e:
        print(f"DIR 방식도 실패: {e}")
        return None


def get_directory_contents_fallback(
    ftp_conn: RobustFTPConnection,
) -> list[tuple[str, bool]]:
    """
    백업 방식: nlst()와 cwd()를 사용하여 디렉토리 내용을 가져옵니다.
    이 방식은 느리지만 호환성이 좋습니다.
    """
    try:
        items = ftp_conn.nlst()
        contents = []

        for item in items:
            if item in (".", ".."):
                continue
            try:
                # 디렉토리인지 확인
                ftp_conn.cwd(item)
                contents.append((item, True))  # 디렉토리
                ftp_conn.cwd("..")
            except Exception:
                contents.append((item, False))  # 파일

        return contents
    except Exception as e:
        print(f"백업 방식도 실패: {e}")
        return []


def generate_ftp_recursive_listing_optimized(
    host: str, username: str, password: str, remote_start_path: str = "/"
) -> Generator[str, None, None]:
    """
    최적화된 FTP 재귀 목록 생성기.
    연결이 끊어지면 자동으로 재연결합니다.
    MLSD -> DIR -> 백업 방식 순으로 시도합니다.
    """
    ftp_conn = None
    try:
        ftp_conn = RobustFTPConnection(host, username, password)

        # 시작 경로를 정규화합니다
        normalized_start_path = remote_start_path.rstrip("/") + "/"

        # 큐 초기화: (현재 FTP 서버의 경로, 현재까지의 상대 경로)
        dirs_to_visit = deque([(normalized_start_path, "")])

        # 사용할 방식 결정 (한 번만 테스트)
        ftp_conn.cwd(normalized_start_path)
        test_contents = get_directory_contents_mlsd(ftp_conn)
        if test_contents is None:
            test_contents = get_directory_contents_dir(ftp_conn)
            if test_contents is None:
                use_method = "fallback"
                print("MLSD와 DIR 모두 실패, 백업 방식 사용")
            else:
                use_method = "dir"
                print("DIR 방식 사용")
        else:
            use_method = "mlsd"
            print("MLSD 방식 사용 (최적화됨)")

        processed_count = 0
        while dirs_to_visit:
            current_ftp_dir, current_relative_path = dirs_to_visit.popleft()

            # 일정 간격으로 연결 상태 확인
            if processed_count % 50 == 0 and processed_count > 0:
                ftp_conn.ensure_connected()

            # FTP 서버에서 현재 디렉터리로 이동
            try:
                ftp_conn.cwd(current_ftp_dir)
            except Exception as e:
                print(f"디렉토리 변경 실패 {current_ftp_dir}: {e}")
                continue

            # 선택된 방식으로 디렉토리 내용 가져오기
            try:
                if use_method == "mlsd":
                    contents = get_directory_contents_mlsd(ftp_conn)
                elif use_method == "dir":
                    contents = get_directory_contents_dir(ftp_conn)
                else:
                    contents = get_directory_contents_fallback(ftp_conn)
            except Exception as e:
                print(f"디렉토리 내용 가져오기 실패 {current_ftp_dir}: {e}")
                continue

            if not contents:
                continue

            for item_name, is_directory in contents:
                # 완전한 경로 생성
                full_item_path = os.path.join(current_relative_path, item_name).replace(
                    "\\", "/"
                )
                final_path = os.path.join(
                    normalized_start_path, full_item_path
                ).replace("\\", "/")

                if is_directory:
                    # 디렉토리
                    final_path = final_path.rstrip("/") + "/"
                    yield final_path
                    # 탐색할 디렉토리 큐에 추가
                    ftp_item_path = os.path.join(current_ftp_dir, item_name).replace(
                        "\\", "/"
                    )
                    dirs_to_visit.append((ftp_item_path + "/", full_item_path + "/"))
                else:
                    # 파일
                    yield final_path

            processed_count += 1

    except Exception as e:
        print(f"FTP 작업 중 오류 발생: {e}")
    finally:
        if ftp_conn:
            ftp_conn.close()


def main() -> None:
    # 명령행 인자 파싱
    parser = argparse.ArgumentParser(description="FTP 디렉토리 재귀 탐색 도구")
    parser.add_argument("host", help="FTP 서버 호스트 주소")
    parser.add_argument("username", help="FTP 사용자명")
    parser.add_argument("-d", "--directory", default="/", help="탐색할 디렉토리 경로 (기본값: /)")
    
    args = parser.parse_args()
    
    print("=== FTP 디렉토리 탐색기 ===")
    
    # 명령행에서 받은 정보
    ftp_host = args.host
    ftp_user = args.username
    ftp_dir = args.directory
    
    # 비밀번호만 입력으로 받기 (보안상)
    ftp_pass = input(f"{ftp_user}@{ftp_host}의 FTP 비밀번호를 입력하세요: ").strip()
    
    print("\n연결 정보:")
    print(f"호스트: {ftp_host}")
    print(f"사용자: {ftp_user}")
    print(f"디렉토리: {ftp_dir}")
    print("=== 최적화된 방식 사용 ===")

    # 실행 시간 측정 시작
    start_time = time.time()

    file_count = 0
    directory_count = 0
    for item in generate_ftp_recursive_listing_optimized(
        ftp_host, ftp_user, ftp_pass, ftp_dir
    ):
        if item.endswith("/"):
            print(f"[디렉토리] {item}")
            directory_count += 1
        else:
            print(f"[파일] {item}")
            file_count += 1

    # 실행 시간 측정 종료
    end_time = time.time()
    execution_time = end_time - start_time

    total_count = file_count + directory_count
    print(f"\n파일 수: {file_count}")
    print(f"디렉토리 수: {directory_count}")
    print(f"전체 개수: {total_count}")
    print(f"실행 시간: {execution_time:.2f}초")
    print(
        f"평균 처리 속도: {total_count / execution_time:.2f} 항목/초"
        if execution_time > 0
        else "평균 처리 속도: N/A"
    )


if __name__ == "__main__":
    main()
