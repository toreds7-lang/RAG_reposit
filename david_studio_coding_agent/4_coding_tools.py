import os


## 1) 폴더/파일 목록 불러오기
def list_files(directory: str = ".") -> str:
    try:
        if not os.path.exists(directory):
            return f"존재하지 않는 경로입니다: {directory}"
        items = []
        for item in sorted(os.listdir(directory)):
            item_path = os.path.join(directory, item)
            if os.path.isdir(item_path):
                items.append(f"[폴더]  {item}/")
            else:
                items.append(f"[파일] {item}")
        if not items:
            return f"비어있는 폴더입니다: {directory}"
        return f"{directory}의 내용:\n" + "\n".join(items)
    except Exception as e:
        return f"폴더/파일 목록을 불러오는 중 오류 발생: {str(e)}"

## 2) 파일 내용 불러오기
def read_file(file_path: str) -> str:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        return ""

def edit_file(file_path: str, old_text: str = "", new_text: str = "") -> str:
    try:
        # 파일이 존재하고 old_text가 주어졌을 때 교체
        if os.path.exists(file_path) and old_text:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if old_text not in content:
                return f"파일에서 텍스트를 찾을 수 없습니다: {old_text}"
            
            content = content.replace(old_text, new_text)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"파일이 성공적으로 수정되었습니다: {file_path}"
        
        # 파일이 없을 경우 새로 생성
        else:
            dir_name = os.path.dirname(file_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_text)
            return f"파일이 성공적으로 생성되었습니다: {file_path}"
    except Exception as e:
        return f"파일 수정 중 오류 발생: {str(e)}"
    
    
if __name__ == "__main__":

    # print("\n[list_files 실행] test_files 폴더 내 파일 목록:")
    # files = list_files("test_files")
    # print(files)

    # print("\n[read_file 실행] test_files/a.py 파일 내용:")
    # content = read_file("test_files/a.py")
    # print(content)

    print("\n[edit_file 실행] test_files/b.py 파일에서 'import math'를 'import math as m'로 변경")
    result = edit_file(
        "test_files/b.py",
        old_text="import math",
        new_text="import math as m"
    )
    print(result)
    print("변경 후 내용:")
    print(read_file("test_files/b.py"))
