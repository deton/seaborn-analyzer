from typing import List, Dict, Tuple
import seaborn as sns
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats
from scipy.stats import distributions
import decimal

class hist():
    DEFAULT_LINECOLORS = ['red', 'darkmagenta', 'mediumblue', 'darkorange',  'pink', 'brown', 'green', 'cyan', 'gold']
    
    def _fit_distribution(x: np.ndarray, distribution: distributions, sigmarange: float, linesplit: int, fit_params: Dict):
        """
        分布のフィッティング

        Parameters
        ----------
        x : ndarray
            フィッティング対象のデータ
        distribution : scipy.stats.distributions
            分布の種類
        sigmarange : float
            フィッティング線の表示範囲（標準偏差の何倍まで表示するか指定）
        linesplit : int
            フィッティング線の分割数（カクカクしたら増やす）
        fit_params : Dict
            フィッティング時に固定するパラメータ
        """
        # 表示範囲指定用に平均と不偏標準偏差計算(正規分布のときを基準に)
        mean = np.mean(x)
        std = np.std(x, ddof=1)

        # フィッティング実行
        params = distribution.fit(x, **fit_params)
        # フィッティング結果のパラメータを分割
        best_params = {'arg': params[:-2],
                      'loc': params[-2],
                      'scale': params[-1]
                      }
        # フィッティング曲線の生成
        Xline = np.linspace(min(mean - std * sigmarange, np.amin(x)), max(mean + std * sigmarange, np.amax(x)), linesplit)
        Yline = distribution.pdf(Xline, loc=best_params['loc'], scale=best_params['scale'], *best_params['arg'])

        # フィッティングの残差平方和を計算 (参考https://rmizutaa.hatenablog.com/entry/2020/02/24/191312)
        hist_y, hist_x = np.histogram(x, bins=20, density=True)  # ヒストグラム化して標準化
        hist_x = (hist_x + np.roll(hist_x, -1))[:-1] / 2.0  # ヒストグラムのxの値をビンの左端→中央に移動
        pred = distribution.pdf(hist_x, loc=best_params['loc'], scale=best_params['scale'], *best_params['arg'])
        rss = np.sum(np.power(pred - hist_y, 2.0))
        # AIC、BICを計算
        k = len(params) - len(fit_params)  # パラメータ数
        n = len(x)  # サンプル数
        # TODO: Fitterライブラリだと対数尤度はhist_xから求めているが、本来の定義ではxから求めるのが適切に見える
        logL = np.sum(distribution.logpdf(x, loc=best_params['loc'], scale=best_params['scale'], *best_params['arg']))  # 対数尤度
        aic = -2 * logL + 2 * k  # AIC
        bic = -2 * logL + k * np.log(n)  # BIC
        # 評価指標()
        fit_scores = {'RSS': rss,
                      'AIC': aic,
                      'BIC': bic
                      }

        return Xline, Yline, best_params, fit_scores
    
    def _round_digits(src: float, rounddigit: int = None, method='decimal'):
        """
        指定桁数で小数を丸める

        Parameters
        ----------
        src : float
            丸め対象の数値
        rounddigit : int
            フィッティング線の表示範囲（標準偏差の何倍まで表示するか指定）
        method : int
            桁数決定手法（'decimal':小数点以下, 'sig':有効数字(Decimal指定), 'format':formatで有効桁数指定）
        """
        if method == 'decimal':
            return round(src, rounddigit)
        elif method == 'sig':
            with decimal.localcontext() as ctx:
                ctx.prec = rounddigit
                return ctx.create_decimal(src)
        elif method == 'format':
            return '{:.{width}g}'.format(src, width=rounddigit)

    @classmethod
    def _round_dict_digits(cls, srcdict: Dict[str, float], rounddigit: int = None, method='decimal'):
        """
        指定桁数でDictの値を丸める

        Parameters
        ----------
        srcdict : Dict[str, float]
            丸め対象のDict
        rounddigit : int
            フィッティング線の表示範囲（標準偏差の何倍まで表示するか指定）
        method : int
            桁数決定手法（'decimal':小数点以下, 'sig':有効数字(Decimal指定), 'format':formatで有効桁数指定）
        """
        dstdict = {}
        for k, v in srcdict.items():
            if rounddigit is not None and isinstance(v, float):
                dstdict[k] = cls._round_digits(v, rounddigit=rounddigit, method=method)
            else:
                dstdict[k] = v
        return dstdict

    @classmethod
    def fit_dist(cls, data: pd.DataFrame, x: str=None, hue=None, dist='norm', ax=None, binwidth=None, bins='auto', norm_hist=True,
                  floc=None, sigmarange=4, linecolor='red', linesplit=200, hist_kws={}):
        """
        分布フィッティングと各指標の表示

        Parameters
        ----------
        data : pd.DataFrame or pd.Series or pd.ndarray
            フィッティング対象のデータ
        x : str
            ヒストグラム作成対象の変数カラム (列名指定、dataがDataFrameのときのみ指定可)
        hue : str
            色分け指定カラム (列名指定、dataがDataFrameのときのみ指定可)
        dist : str or List[str]
            分布の種類 ("norm", "lognorm", "gamma", "t", "expon", "uniform", "chi2", "weibull")
        ax : matplotlib.axes._subplots.Axes
            表示対象のax (Noneならplt.plotで1枚ごとにプロット)
        binwidth : float
            ビンの幅 (binsと共存不可)
        bins : int
            ビンの数 (bin_widthと共存不可、'auto'とするとスタージェスの公式で自動決定)
        norm_hist : bool
            ヒストグラムを面積1となるよう正規化するか？
        floc : float
            フィッティング時のX方向オフセット (Noneなら指定なし(weibullとexponは0))
        sigmarange : float
            フィッティング線の表示範囲 (標準偏差の何倍まで表示するか指定)
        linecolor : str or List[str]
            フィッティング線の色指定 (複数分布フィッティング時は、List指定)
        linesplit : int
            フィッティング線の分割数 (カクカクしたら増やす)
        hist_kws : Dict
            ヒストグラム表示(seaborn.histplot)の引数
        """

        # 描画用axがNoneのとき、matplotlib.pyplot.gca()を使用
        if ax == None:
            ax=plt.gca()
        
        # スタイルを変更 (デフォルト設定は見づらいため)
        if 'alpha' not in hist_kws.keys():
            hist_kws['alpha'] = 0.7
        if 'edgecolor' not in hist_kws.keys():
            hist_kws['edgecolor'] = 'white'

        # フィッティング対象データをndarrayで抽出
        if isinstance(data, pd.DataFrame):
            X = data[x].values
        elif isinstance(data, pd.Series):
            X = data.values
        elif isinstance(data, np.ndarray):
            X = data
        # フィッティング対象データの最小値よりflocが大きい場合、エラーを出す
        if floc is not None and floc >= np.amin(X):
            raise Exception('floc must be larger than minimum of data')

        # ビンサイズを設定
        if binwidth is not None:
            if bins == 'auto':
                bins = np.arange(np.floor(X.min()), np.ceil(X.max()), binwidth)
            else: # binsとbin_widthは同時指定できない
                raise Exception('arguments "bins" and "binwidth" cannot coexist')

        # norm_hist=Trueのとき、statをdensityに指定 (histplotの引数)
        stat = 'density' if norm_hist else 'count'
        # 色分けあるとき、ヒストグラム種類を積み上げに指定 (histplotの引数)
        multiple = 'layer' if hue is None else 'stack'

        # ヒストグラム描画
        ax = sns.histplot(data, x=x, hue=hue, ax=ax, bins=bins, stat=stat, multiple=multiple, **hist_kws)

        # 色分けあるとき、凡例を左上に表示
        if hue is not None:
            lg = ax.legend_
            handles = lg.legendHandles
            labels = [t.get_text() for t in lg.texts]
            leg_hist = ax.legend(handles, labels, loc='upper left')
            ax.add_artist(leg_hist)

        # distをList化
        dists = [dist] if isinstance(dist, str) else dist
        # フィッティング線の色指定をリスト化
        linecolor = [linecolor] if isinstance(linecolor, str) else linecolor
        # 2種類以上をプロットしており、かつ色指定がListでないとき、他の色を追加
        if len(dists) >= 2:
            if len(linecolor) == 1:
                linecolor = cls.DEFAULT_LINECOLORS
            elif len(dists) != len(linecolor):
                raise Exception('length of "linecolor" must be equal to length of "dist"')

        # 分布をフィッティング
        all_params = {}
        all_scores = {}
        line_legends = []
        for i, distribution in enumerate(dists):
            fit_params = {}
            # 分布が文字列型のとき、scipy.stats.distributionsに変更
            if isinstance(distribution, str):
                if distribution == 'norm':
                    distribution = stats.norm
                elif distribution == 'lognorm':
                    distribution = stats.lognorm
                elif distribution == 'gamma':
                    distribution = stats.gamma
                elif distribution == 't':
                    distribution = stats.t
                elif distribution == 'expon':
                    distribution = stats.expon
                    fit_params = {'floc': 0} # 指数分布のとき、locationパラメータを0で固定
                elif distribution == 'uniform':
                    distribution = stats.uniform
                elif distribution == 'chi2':
                    distribution = stats.chi2
                    fit_params = {'floc': 0,  # カイ二乗分布のとき、locationパラメータを0で固定
                                  'fscale': 1,  # カイ二乗分布のとき、scaleパラメータを1で固定
                                  }
                elif distribution == 'weibull':
                    distribution = stats.weibull_min
                    fit_params = {'floc': 0} # ワイブル分布のとき、locationパラメータを0で固定
            # flocしているとき、X方向オフセットを指定値で固定
            if floc is not None:
                fit_params['floc'] = floc
            # 分布フィット
            xline, yline, best_params, fit_scores = cls._fit_distribution(X, distribution, sigmarange, linesplit, fit_params)

            # 標準化していないとき、ヒストグラムと最大値の8割を合わせるようフィッティング線の倍率調整
            if norm_hist is False:
                line_max = np.amax(yline)
                hist_max = ax.get_ylim()[1]
                yline = yline * hist_max / line_max * 0.8
            # フィッティング線の描画
            leg, = ax.plot(xline, yline, color=linecolor[i])
            line_legends.append(leg)

            # フィッティング結果パラメータをdict化
            params = {}
            # 正規分布
            if distribution == stats.norm:
                params['mean'] = best_params['loc']
                params['std'] = best_params['scale']
                all_params['norm'] = params
                all_scores['norm'] = fit_scores  # フィッティングの評価指標
            # 対数正規分布 (通常の対数正規分布＋x方向オフセット、参考https://analytics-note.xyz/statistics/scipy-lognorm/)
            elif distribution == stats.lognorm:
                params['mu'] = np.log(best_params['scale'])
                params['sigma'] = best_params['arg'][0]
                params['loc'] = best_params['loc']
                all_params['lognorm'] = params
                all_scores['lognorm'] = fit_scores  # フィッティングの評価指標
            # ガンマ分布 (通常のガンマ分布＋x方向オフセット、参考https://qiita.com/kidaufo/items/2a5ba5a4bf100dc0f106)
            elif distribution == stats.gamma:
                params['theta'] = best_params['scale']
                params['k'] = best_params['arg'][0]
                params['loc'] = best_params['loc']
                all_params['gamma'] = params
                all_scores['gamma'] = fit_scores  # フィッティングの評価指標
            # 指数分布 (オフセットなし、参考https://stackoverflow.com/questions/25085200/scipy-stats-expon-fit-with-no-location-parameter)
            elif distribution == stats.expon:
                params['lambda'] = best_params['scale']
                all_params['expon'] = params
                all_scores['expon'] = fit_scores  # フィッティングの評価指標
            # ワイブル分布 (オフセットなし、参考https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.weibull_min.html)
            elif distribution == stats.weibull_min:
                params['lambda'] = best_params['scale']
                params['k'] = best_params['arg'][0]
                all_params['weibull'] = params
                all_scores['weibull'] = fit_scores  # フィッティングの評価指標
            # 一様分布 (x方向オフセット＋x方向倍率、参考https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.uniform.html)
            elif distribution == stats.uniform:
                params['scale'] = best_params['scale']
                params['loc'] = best_params['loc']
                all_params['uniform'] = params
                all_scores['uniform'] = fit_scores  # フィッティングの評価指標
            # t分布 (通常のt分布＋x方向オフセット＋x方向倍率、参考https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html)
            elif distribution == stats.t:
                params['scale'] = best_params['scale']
                params['df'] = best_params['arg'][0]
                params['loc'] = best_params['loc']
                all_params['t'] = params
                all_scores['t'] = fit_scores  # フィッティングの評価指標
            # カイ二乗分布 (オフセット・倍率なし、参考https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.chi2.html)
            elif distribution == stats.chi2:
                params['df'] = best_params['arg'][0]
                all_params['chi2'] = params
                all_scores['chi2'] = fit_scores  # フィッティングの評価指標
            
        # フィッティング線の凡例をプロット (2色以上のときのみ)
        if len(dists) >= 2:
            line_labels = [str(d) for d in dists]
            ax.legend(line_legends, line_labels, loc='upper right')

        return all_params, all_scores



    @classmethod
    def plot_normality(cls, data: pd.DataFrame, x: str=None, hue=None, binwidth=None, bins='auto', norm_hist=False,
                        sigmarange=4, linecolor='red', linesplit=200, rounddigit=5,
                        hist_kws={}, subplot_kws={}):
        """
        正規性検定プロット

        Parameters
        ----------
        data : pd.DataFrame or pd.Series or pd.ndarray
            フィッティング対象のデータ
        x : str
            ヒストグラム作成対象の変数カラム (列名指定、dataがDataFrameのときのみ指定可)
        hue : str
            色分け指定カラム (列名指定、dataがDataFrameのときのみ指定可)
        binwidth : float
            ビンの幅 (binsと共存不可)
        bins : int
            ビンの数 (bin_widthと共存不可、'auto'とするとスタージェスの公式で自動決定)
        norm_hist : bool
            ヒストグラムを面積1となるよう正規化するか？
        sigmarange : float
            フィッティング線の表示範囲 (標準偏差の何倍まで表示するか指定)
        linecolor : str
            フィッティング線の色指定
        linesplit : int
            フィッティング線の分割数 (カクカクしたら増やす)
        rounddigit: int
            表示指標の小数丸め桁数
        hist_kws : Dict
            ヒストグラム表示(matplotlib.axes.Axes.hist())の引数
        subplot_kws : Dict
            プロット用のplt.subplots()に渡す引数 (例：figsize)
        """

        # 描画用のsubplots作成
        if 'figsize' not in subplot_kws.keys():
            subplot_kws['figsize'] = (6, 12)
        fig, axes = plt.subplots(2, 1, **subplot_kws)

        # QQプロット描画
        if isinstance(data, pd.DataFrame):
            X = data[x].values
        elif isinstance(data, pd.Series):
            X = data.values
        elif isinstance(data, np.ndarray):
            X = data
        stats.probplot(X, dist='norm', plot=axes[0])

        # ヒストグラムとフィッティング線を描画
        cls.fit_dist(data, x=x, hue=hue, dist='norm', ax=axes[1], binwidth=binwidth, bins=bins, norm_hist=norm_hist,
                      sigmarange=sigmarange, linecolor=linecolor, linesplit=linesplit, hist_kws=hist_kws)
        # 平均と不偏標準偏差を計算し、ヒストグラム図中に記載
        mean = np.mean(X)
        std = np.std(X, ddof=1)
        params = {'mean':mean,
                  'std':std
                  }
        param_list = [f'{k}={v}' for k, v in cls._round_dict_digits(params, rounddigit, 'sig').items()]
        param_text = "\n".join(param_list)
        axes[1].text(axes[1].get_xlim()[0] + (axes[1].get_xlim()[1] - axes[1].get_xlim()[0]) * 0.95,
                     axes[1].get_ylim()[1] * 0.9,
                     param_text, verticalalignment='top', horizontalalignment='right')

        # 正規性検定
        if len(X) <= 2000: # シャピロウィルク検定 (N<=2000のとき)
            method = 'shapiro-wilk'
            normality=stats.shapiro(X)
        else: # コルモゴロフ-スミルノフ検定 (N>2000のとき)
            method = 'kolmogorov-smirnov'
            normality = stats.kstest(X, stats.norm(loc=mean, scale=std).cdf)
        # 検定結果を図中に記載
        params = {'statistic':normality.statistic,
                  'pvalue':normality.pvalue,
                  }
        param_list = [f'{k}={v}' for k, v in cls._round_dict_digits(params, rounddigit, 'sig').items()]
        param_list.insert(0, f'method={method}')
        param_text = "\n".join(param_list)
        axes[0].text(axes[0].get_xlim()[0] + (axes[0].get_xlim()[1] - axes[0].get_xlim()[0]) * 0.95,
                     axes[0].get_ylim()[0] + (axes[0].get_ylim()[1] - axes[0].get_ylim()[0]) * 0.1,
                     param_text, verticalalignment='bottom', horizontalalignment='right')