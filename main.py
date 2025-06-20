import argparse
import os
import time
from collections import deque
from typing import Generator

from robust_ftp import RobustFTPConnection


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
            if not line.strip():
                continue
                
            # 다양한 FTP 서버 형식 지원을 위한 개선된 파싱
            parts = line.split(None, 8)  # 최대 8번만 분리
            if len(parts) < 4:  # 최소한 권한, 링크수, 소유자, 파일명이 있어야 함
                continue
                
            permissions = parts[0]
            is_dir = permissions.startswith("d")
            
            # 파일명 추출 - 마지막 부분에서 링크 표시 제거
            filename = parts[-1]
            
            # 심볼릭 링크 처리 (filename -> target 형식)
            if " -> " in filename:
                filename = filename.split(" -> ")[0]
            
            if filename in (".", ".."):
                continue
                
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
