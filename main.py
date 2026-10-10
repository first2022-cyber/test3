import io
import urllib.request
import zipfile

import pandas as pd
import plotly.express as px
import streamlit as st


# ------------------------------------------------------------
# 기본 설정: 앱 제목과 따뜻한 색상 테마를 지정합니다.
# ------------------------------------------------------------
st.set_page_config(
    page_title="데이터의 퍼짐 살펴보기",
    page_icon="📊",
    layout="wide",
)

DATA_URL = (
    "https://raw.githubusercontent.com/first2022-cyber/contents/"
    "2d44987ed9a17e9046bcf584db9f6ea2e2543dfe/"
    "population_ts_yearly_gender.zip"
)


@st.cache_data(show_spinner="인구 데이터를 불러오는 중입니다...")
def load_population_data():
    """ZIP 파일을 내려받아 CSV를 읽고, 최신 연도의 총인구를 계산합니다."""
    # 표준 라이브러리로 ZIP 파일을 내려받으므로 별도 다운로드 패키지가 필요 없습니다.
    request = urllib.request.Request(
        DATA_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        zip_bytes = response.read()

    # ZIP 안에 들어 있는 CSV 파일을 찾습니다.
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        csv_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv") and not name.startswith("__MACOSX/")
        ]
        if not csv_files:
            raise ValueError("ZIP 파일 안에서 CSV 파일을 찾을 수 없습니다.")

        # CSV가 여러 개라면 첫 번째 CSV 파일을 사용합니다.
        csv_bytes = archive.read(csv_files[0])

    # 한글 CSV에서 흔히 쓰이는 인코딩을 순서대로 시도합니다.
    data = None
    last_error = None
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            data = pd.read_csv(io.BytesIO(csv_bytes), encoding=encoding, low_memory=False)
            break
        except UnicodeDecodeError as error:
            last_error = error

    if data is None:
        raise ValueError(f"CSV 인코딩을 확인할 수 없습니다: {last_error}")

    # 연도 열에서 숫자만 뽑아 가장 최신 연도를 찾습니다.
    if "연도" not in data.columns:
        raise ValueError("데이터에 '연도' 열이 없습니다.")

    year_number = pd.to_numeric(
        data["연도"].astype(str).str.extract(r"(\d{4})", expand=False),
        errors="coerce",
    )
    if year_number.notna().sum() == 0:
        raise ValueError("'연도' 열에서 연도 숫자를 읽을 수 없습니다.")

    latest_year = int(year_number.max())
    data = data.loc[year_number == latest_year].copy()

    # '남_'과 '여_'로 시작하는 모든 연령별 인구 열을 숫자로 바꿉니다.
    male_columns = [column for column in data.columns if str(column).startswith("남_")]
    female_columns = [column for column in data.columns if str(column).startswith("여_")]
    population_columns = male_columns + female_columns

    if not population_columns:
        raise ValueError("'남_' 또는 '여_'로 시작하는 인구 열을 찾을 수 없습니다.")

    for column in population_columns:
        # 천 단위 쉼표가 문자열로 들어온 경우를 고려해 쉼표를 제거합니다.
        data[column] = pd.to_numeric(
            data[column].astype(str).str.replace(",", "", regex=False),
            errors="coerce",
        ).fillna(0)

    # 동네(행)별 남성 인구와 여성 인구를 모두 더해 총인구를 만듭니다.
    data["총인구"] = data[population_columns].sum(axis=1)

    return data, latest_year


# ------------------------------------------------------------
# 화면 제목과 간단한 안내 문구
# ------------------------------------------------------------
st.title("📊 데이터의 퍼짐 살펴보기")
st.write(
    "전국 읍·면·동의 **총인구가 얼마나 다양하게 퍼져 있는지** "
    "요약 통계, 히스토그램, 상자그림으로 살펴봅니다."
)

try:
    df, latest_year = load_population_data()
except Exception as error:
    st.error("데이터를 불러오거나 처리하는 중 문제가 발생했습니다.")
    st.exception(error)
    st.stop()

st.caption(f"분석 연도: **{latest_year}년** · 분석한 읍·면·동 수: **{len(df):,}개**")

# ------------------------------------------------------------
# 1. 총인구 describe() 요약 통계
# ------------------------------------------------------------
st.header("1. 총인구 요약 통계")
st.write(
    "아래 표는 `describe()` 결과입니다. 평균과 표준편차, 최솟값과 최댓값 등을 "
    "통해 인구 규모가 어느 정도인지 확인할 수 있습니다."
)

summary = df["총인구"].describe()
# 통계 항목 이름을 한국어로 바꿉니다.
summary = summary.rename(index={
    "count": "데이터 개수",
    "mean": "평균",
    "std": "표준편차",
    "min": "최솟값",
    "25%": "1사분위수(25%)",
    "50%": "중앙값(50%)",
    "75%": "3사분위수(75%)",
    "max": "최댓값",
})
summary_table = summary.to_frame(name="총인구").round(2)
st.dataframe(summary_table, use_container_width=True)

# ------------------------------------------------------------
# 공통 그래프 디자인: 크림색 배경과 따뜻한 주황색을 사용합니다.
# ------------------------------------------------------------
warm_layout = dict(
    template="plotly_white",
    paper_bgcolor="#FFF9F2",
    plot_bgcolor="#FFF9F2",
    font=dict(family="Arial, sans-serif", color="#49382D"),
    margin=dict(l=35, r=25, t=55, b=45),
)

# ------------------------------------------------------------
# 2. 히스토그램
# ------------------------------------------------------------
st.header("2. 총인구 히스토그램")
st.write(
    "가로축은 읍·면·동의 총인구, 세로축은 해당 인구 구간에 속하는 "
    "읍·면·동의 개수입니다. 막대가 높은 구간에 지역이 많이 모여 있습니다."
)

histogram = px.histogram(
    df,
    x="총인구",
    nbins=40,
    labels={"총인구": "총인구(명)", "count": "읍·면·동 개수"},
    title=f"{latest_year}년 읍·면·동별 총인구 분포",
    color_discrete_sequence=["#E99A68"],
)
histogram.update_layout(**warm_layout, bargap=0.08, showlegend=False)
histogram.update_xaxes(title="총인구(명)", tickformat=",")
histogram.update_yaxes(title="읍·면·동 개수")
st.plotly_chart(histogram, use_container_width=True)

# ------------------------------------------------------------
# 3. 상자그림
# ------------------------------------------------------------
st.header("3. 총인구 상자그림")
st.write(
    "상자 안의 가운데 선은 중앙값이고, 상자의 아래·위 경계는 1사분위수와 "
    "3사분위수입니다. 점으로 표시된 값은 다른 지역보다 인구가 특히 많거나 "
    "적은 지역일 수 있습니다. 그래프 위에 마우스를 올리면 값을 확인할 수 있습니다."
)

box_plot = px.box(
    df,
    y="총인구",
    points="outliers",
    labels={"총인구": "총인구(명)"},
    title=f"{latest_year}년 읍·면·동별 총인구 상자그림",
    color_discrete_sequence=["#D97845"],
)
box_plot.update_layout(**warm_layout, showlegend=False)
box_plot.update_yaxes(title="총인구(명)", tickformat=",")
st.plotly_chart(box_plot, use_container_width=True)

# ------------------------------------------------------------
# 초보자용 참고: Plotly 그래프는 확대·축소, 이동, 값 확인이 가능합니다.
# ------------------------------------------------------------
st.info(
    "그래프 사용 팁: 마우스 휠이나 그래프 도구 모음으로 확대·축소하고, "
    "막대나 점 위에 마우스를 올려 값을 확인해 보세요."
)
