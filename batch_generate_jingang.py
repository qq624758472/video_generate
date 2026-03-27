import argparse
from pathlib import Path

import test


test.TIMEOUT = 1800
test.POLL_INTERVAL = 5


NEGATIVE_PROMPT = (
    "不要仙气特效、不要金色光环、不要悬浮粒子、不要玄幻法术、不要夸张神圣光、"
    "不要现代建筑、不要现代服饰、不要卡通感、不要游戏CG感、不要高饱和网红色调、"
    "不要夸张表情、不要快速剪辑"
)


COMMON_STYLE = (
    "写实禅意、纪实电影感、沉静克制、低饱和、自然光、慢节奏、平视镜头、"
    "无神话特效、无光环、无夸张表演、古印度背景、16:9横屏"
)


SCENES = [
    (
        "jing1",
        "清晨微光中的石窟内部，一只布满岁月痕迹的手轻轻抚过刻有经文的贝叶经，"
        "手指停在“如是我闻”四字上，烛火轻轻摇曳，镜头从经文特写缓慢后拉，"
        "露出阿难尊者身着素色袈裟，垂目静坐，身后一众比丘安静记录经文，"
        "石壁古朴，空气安静，柔光，浅景深逐渐转为深景深，庄重沉静。"
    ),
    (
        "jing2",
        "两千多年前古印度清晨，晨雾笼罩的舍卫国郊野，娑罗树与芒果林连绵，"
        "阳光穿过薄雾形成柔和光束，林间隐约可见祇树给孤独园的僧团寮房，"
        "远处是舍卫国城墙轮廓，天空泛着鱼肚白，真实航拍，极慢移动，古朴安静。"
    ),
    (
        "jing3",
        "古印度僧团寮房外的清晨，木门陆续被轻轻推开，身着褐红袈裟的比丘们安静有序走出房间，"
        "有人整理袈裟，有人擦拭钵盂，动作缓慢沉稳，无人喧哗，落叶铺地，"
        "镜头平视跟随，庄严却日常，长镜头纪实感。"
    ),
    (
        "jing4",
        "寮房中央木门被轻轻推开，佛陀缓步走出，面容平和，神情沉静。"
        "分切镜头表现双手缓缓整理并披好素色袈裟，双手捧起朴素陶钵，"
        "赤脚踩在微凉石板上，动作极稳极慢，专注当下，细节真实，浅景深。"
    ),
    (
        "jing5",
        "佛陀走在僧团最前方，身后比丘众整齐列队，赤脚持钵，缓步走向舍卫城。"
        "镜头侧面长跟拍，队伍穿过城门后进入市井，街边有商贩、妇人、孩童、婆罗门、乞丐，"
        "众生百态自然展开，民众见僧团后有人合十、有人递食，佛陀与比丘平和回礼。"
    ),
    (
        "jing6",
        "交叉蒙太奇，佛陀沿街次第乞食。贫苦土坯房前，衣衫破旧的妇人从陶罐里盛出少量糙米，"
        "恭敬放入佛陀钵中，佛陀垂目合十平等接受。富户门前，家仆端来丰盛食物，"
        "佛陀只取足够一餐的分量。其他比丘逐户依次乞食，不分贫富，不择门户。"
    ),
    (
        "jing7",
        "正午前明亮而柔和的阳光下，佛陀与比丘众列队从舍卫城返回祇树给孤独园，"
        "镜头从背后缓缓跟拍，众人影子被阳光拉在地面上，脚步整齐，持钵而行，无人交谈，"
        "身后的市井喧闹渐渐远去，前方重新进入树林和宁静园林。"
    ),
    (
        "jing8",
        "林间空地上，佛陀与比丘们静坐用餐。分切特写：佛陀缓慢安静用餐，不浪费一粒食物；"
        "用餐完毕后细致擦拭并收好钵盂，整齐叠放衣物；随后赤脚走到溪边，"
        "双手捧水清洗双足，尘土顺水流走，细节朴素真实，微距质感。"
    ),
    (
        "jing9",
        "佛陀洗足后回到大树下，亲手铺开草席，整理座垫，缓缓结跏趺坐，垂目收心，"
        "身姿安稳如古树，身后比丘众静坐，阳光穿过树叶洒下斑驳光影，林间寂静，"
        "镜头从中景极慢拉远到全景，最后停在佛陀平和沉静的侧脸。"
    ),
]


def build_prompt(scene_prompt: str) -> str:
    return f"{scene_prompt}{COMMON_STYLE}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="批量生成《金刚经》分镜视频")
    parser.add_argument("--start-index", type=int, default=1, help="从第几个分镜开始，1-based")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = Path("generated_jingang")
    out_dir.mkdir(exist_ok=True)

    generator = test.VideoGenerator(
        api_key=test.API_KEY,
        base_url=test.BASE_URL,
    )

    start_index = max(args.start_index, 1) - 1
    for output_name, scene_prompt in SCENES[start_index:]:
        prompt = build_prompt(scene_prompt)
        metadata = {
            "quality_level": "high",
            "negative_prompt": NEGATIVE_PROMPT,
        }

        print(f"\\n===== 开始生成 {output_name} =====")
        task_id = generator.create_video_task(
            model="sora-2",
            prompt=prompt,
            duration=15,
            width=1920,
            height=1080,
            fps=24,
            metadata=metadata,
        )
        if not task_id:
            print(f"{output_name} 创建失败，跳过")
            continue

        task_status = generator.wait_for_task_complete(task_id)
        if task_status != "completed":
            print(f"{output_name} 未完成，跳过下载")
            continue

        save_path = out_dir / f"{output_name}_{task_id}.mp4"
        ok = generator.download_video(task_id=task_id, save_path=str(save_path))
        if not ok:
            print(f"{output_name} 下载失败")
        else:
            print(f"{output_name} 已保存到 {save_path}")


if __name__ == "__main__":
    main()
