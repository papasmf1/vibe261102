# Developer라는 개발자 클래스를 정의하려고함. 
# 내부에 id, title, skill변수가 있고, 이 내용을 출력하는
# printInfo()메서드가 필요해
class Developer:
    def __init__(self, id, title, skill):
        self.id = id
        self.title = title
        self.skill = skill

    def printInfo(self):
        print(f"ID: {self.id}, Title: {self.title}, Skill: {self.skill}")

#인스턴스를 생성(디버깅하는 모드로 실행하면 중단점)
dev = Developer(1, "Backend Developer", "Python")
dev.printInfo() 


