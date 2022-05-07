import pyupbit
import time
import datetime
import telegram
import pandas

# Telegram
telegram_token = "telegram_token"
telegram_chat_id = "telegram_chat_id"
telegram_bot = telegram.Bot(token=telegram_token)

def telegram_send(message):
    telegram_bot.sendMessage(chat_id=telegram_chat_id, text=message)

def rsi(ohlc: pandas.DataFrame, period: int = 14):
    delta = ohlc["close"].diff()
    ups, downs = delta.copy(), delta.copy()
    ups[ups < 0] = 0
    downs[downs > 0] = 0
    
    AU = ups.ewm(com = period-1, min_periods = period).mean()
    AD = downs.abs().ewm(com = period-1, min_periods = period).mean()
    RS = AU/AD
    
    return pandas.Series(100 - (100/(1 + RS)), name = "RSI")

TICKER = 'KRW-BTC'
INTERVAL = 'minute3'
if INTERVAL == 'minute1':
    CANDLE = 1  # INTERVAL과 맞춤 (봉 시간 설정, minute 기준)
    CANDLE_REMAIN = 0  # 분봉마다 타겟 갱신시 거래중지 minute 설정 (line 75)
elif INTERVAL == 'minute3':
    CANDLE = 3
    CANDLE_REMAIN = 2
elif INTERVAL == 'minute5':
    CANDLE = 5
    CANDLE_REMAIN = 4
elif INTERVAL == 'minute10':
    CANDLE = 10
    CANDLE_REMAIN = 9
elif INTERVAL == 'minute15':
    CANDLE = 15
    CANDLE_REMAIN = 14
elif INTERVAL == 'minute30':
    CANDLE = 30
    CANDLE_REMAIN = 29
elif INTERVAL == 'minute60':
    CANDLE = 60
    CANDLE_REMAIN = 59
else:
    print("CANDLE_REMAIN set error!!")
    exit()
KVALUE = 0.1  # k값 by 백테스팅
TSTOP_MIN = 1.007  # 최소 0.7% 이상 수익이 발생한 경우에 Traillig Stop 동작
TSTOP_GAP = 1.0025  # 최고점 대비 0.25% 하락시 익절 값

TSTOP = TSTOP_MIN  # 텔레그램 전송 트레일링스탑 발동 값
TSTOP_MSG = 0.9975  # 텔레그램 전송 트레일링스탑 익절 값

AFTER_BUY = 0.97
SLOSS = 0.995  # 스탑로스 손절 값 0.2%

def cal_target(ticker):  # 타겟 금액 리턴
    df = pyupbit.get_ohlcv(ticker, INTERVAL)  # 봉 산출
    ago = df.iloc[-2]  # 1봉 전
    current = df.iloc[-1]  # 현재 봉
    range = ago['high'] - ago['low']  # 변동폭 산출
    target = current['open'] + range * KVALUE  # target calculate
    return target

def cal_open_price(ticker):  # 시가 리턴
    df = pyupbit.get_ohlcv(ticker, INTERVAL)  # 봉 호출
    current = df.iloc[-1]  # 현재 봉
    open_price = current['open']  # 시가 산출
    return open_price

def cal_high_price(ticker):  # 고가 리턴
    df = pyupbit.get_ohlcv(ticker, INTERVAL == 'minute15')  # 봉  호 출
    current = df.iloc[-1]  # 현재 봉
    high_price = current['high']  # 고가 산출
    return high_price

def get_ma5(ticker):  # INTERVAL 기준 5봉 이동 평균선 조회
    df = pyupbit.get_ohlcv(ticker, INTERVAL)
    ma = df['close'].rolling(5).mean()
    return ma[-1]

def print_balance(upbit):  # 보유 잔고 출력
    balances = upbit.get_balances()  # 보유 잔고 산출
    print('\n<<< holding Price >>>')
    for balance in balances:
        print(balance['currency'], ':', balance['balance'])
    print('now TIME:', datetime.datetime.now())
    print('\n')

def up_down(price, price_open):  # 상승장 하락장 리턴
    return '▲BULL' if price > price_open else '▽bear'


# Login to Upbit
def login():  # 로그인
    f = open('./key.txt', 'r')
    lines = f.readlines()
    access = lines[0].strip()  # access key
    secret = lines[1].strip()  # secret key
    f.close()

    try:
        upbit = pyupbit.Upbit(access, secret)  # class instance object
        print('Welcome [ M A N S U rrr ] -- Upbit Auto Trading --', time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
    except:
        print('Upbit login error!!')
        exit()

    print_balance(upbit)  # 로그인 당시 전체 잔고 출력

    return upbit


upbit = login()  # 로그인

# 초기화
target = cal_target(TICKER)
price = pyupbit.get_current_price(TICKER)  # 프로그램 시작시 종목 현재가 산출
hold_check = upbit.get_balance(TICKER)
price_open = cal_open_price(TICKER)  # 시가 저장
price_high = cal_high_price(TICKER)  # 고가 저장
ticker_balance = upbit.get_balance(TICKER)  # 종목 보유량 저장
ma5 = get_ma5(TICKER)
i = 0

if price <= target:  # 프로그램 시작시 매수진행 check (동작 상태 OK check)
    op_mode = True
else:
    op_mode = False

if hold_check == 0 and hold_check != None:  # 프로그램 시작시 종목보유 check (종목 보유기간동안 재시작 대처)
    hold = False  # 현재 코인 보유 여부
else:
    hold = True

# 프로그램 시작 당시 시드머니 저장 (다중 실행시 시드머니 기준의 n배 매수 필요)
seed_money = upbit.get_balance('KRW')

while True:
    try:
        now = datetime.datetime.now()
        price = pyupbit.get_current_price(TICKER)  # 매 초 현재가 호출
        ticker_balance = upbit.get_balance(TICKER)  # 보유 코인 잔고 저장
        target = cal_target(TICKER)
        hold_check = upbit.get_balance(TICKER)
        krw_balance = upbit.get_balance('KRW')  # 보유 원화 저장
        avg = upbit.get_avg_buy_price(TICKER)  # 매수 평균 가
        ma5 = get_ma5(TICKER)
        price_open = cal_open_price(TICKER)  # 시가 저장
        price_high = cal_high_price(TICKER)  # 고가 저장
        data = pyupbit.get_ohlcv(TICKER, interval="minute3")  # rsi 데이타
        sell_data = pyupbit.get_ohlcv(TICKER, interval="minute60")  # sell_rsi 데이타
        now_rsi = rsi(data, 14).iloc[-1]  # rsi
        sell_rsi = rsi(sell_data, 14).iloc[-1]  # sell_rsi
        time.sleep(0.5)
        
        # 익절 매도  (sell_rsi > 65)
        if ((price / avg) > TSTOP_MIN > TSTOP_GAP <= (price_high / price)):
            if op_mode is True and hold is True and price is not None:
                upbit.sell_market_order(TICKER, ticker_balance)  # 보유 코인 전량 시장가 매도
                print('ALL COIN - sell OK!!')
                telegram_send('■■■■■■■■\n 수익실현 ~!!\n 전량매도 ^-^+\n■■■■■■■■')
                hold = False  # 보유여부 False 변경
            op_mode = False  # 타겟 갱신시까지 거래 잠시 중지

        # 매도 - 봉의 종가지점에서 전량매도
        # if (now.minute % CANDLE == CANDLE_REMAIN) and (50 <= now.second <= 59):
        #    if op_mode is True and hold is True:
        #        upbit.sell_market_order(TICKER, ticker_balance)  # 보유 코인 전량 시장가 매도
        #        print('ALL COIN - sell OK!!')
        #        hold = False  # 보유여부 False 변경
        #    op_mode = False  # 타겟 갱신시까지 거래 잠시 중지

        # 봉 넘긴 후(op_mode = False) 5초 텀

        # hh:mm:05 목표가 갱신
        # 매 봉의 5초~10초 타겟, 시가, 동작상태 ON, 이평선 계산, 보유잔고 출력
        if (now.minute % CANDLE == 0) and (3 <= now.second <= 7):
            target = cal_target(TICKER)
            price_open = cal_open_price(TICKER)
            op_mode = True
            ma5 = get_ma5(TICKER)
            print_balance(upbit)

        # 매 초마다 조건 확인후 매수 시도  sell_rsi < 35
        if op_mode is True and hold is False and price is not None and price >= target and price_open > ma5:
            # 매수
            krw_balance = upbit.get_balance('KRW')  # 보유 원화 저장
            upbit.buy_market_order(TICKER, krw_balance * 0.99)  # 보유 원화(시드머니)의 n배만큼 시장가 매수 (24%)
            print('target COIN - buy OK!!')
            telegram_send('₩ ₩ ₩ ₩ ₩ ₩ ₩ ₩\n 신호포착\n 매수완료!!\n₩ ₩ ₩ ₩ ₩ ₩ ₩ ₩')
            hold = True  # 보유여부 True 변경

        # 스탑로스 %하락시 강제 매도 후 일시중지
        if op_mode is True and hold is True and price is not None and ((price / avg) < SLOSS):
            upbit.sell_market_order(TICKER, ticker_balance)  # 보유 코인 전량 시장가 매도
            print('stop Loss SELL.. T.T')
            telegram_send('T.T.T.T.T.T.T.T\n( 스탑로스 매도체결.. T.T )\nT.T.T.T.T.T.T.T')
            hold = False  # 보유여부 False 변경
            op_mode = False  # 일시중지
            time.sleep(0.5)
    except:
        print('error - error !!')
        telegram_send('########\n########\n error !!\n########\n########')
        time.sleep(10)

    # 상태 출력
    if i == 10:
        print(f"■ now TIME - {now.hour}:{now.minute}:{now.second} << {TICKER} >>")
        telegram_send(f"■ 현재시간 - {now.hour}:{now.minute}:{now.second} << {TICKER} >>")
        print(f"focusP: {target} | nowP: {price} | inSIGN: {price_open > ma5} | Holding: {hold} | working: {op_mode}")
        telegram_send(f"목표가 : {target} / 현재가 : {price} / 시작가 : {price_open} / 종목보유량 : {ticker_balance} / 수익현황KRW : {upbit.get_balance('KRW') - seed_money} / 보유상태 : {hold}")
        print(f"return KRW: {upbit.get_balance('KRW') - seed_money} | holdind NUM: {ticker_balance} | target WIN: {price >= target} | startP: {price_open} | market:{up_down(price, price_open)}")
        telegram_send(f"진입신호 : {price_open > ma5} / 목표가 돌파 : {price >= target} / 동작상태 : {op_mode} / 시장현황 : {up_down(price, price_open)}")
        i = 0
    i += 1
    time.sleep(1)
