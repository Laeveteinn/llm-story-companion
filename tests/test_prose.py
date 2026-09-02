from writing_runtime.prose import ProseAnalyzer, calibrate
SAMPLE=('Rain hit the shutters hard. Mara crossed the room, stopped, and listened. '
        'Something moved below the window, slow enough to be deliberate. She killed the lamp. '
        'For three breaths, the house held still. Then the latch lifted. ')*20
def test_metrics_are_deterministic():
    a=ProseAnalyzer(); x=a.analyze(SAMPLE).as_dict(); y=a.analyze(SAMPLE).as_dict(); assert x==y
    assert x['metrics']['word_count']>100
def test_calibration():
    p=calibrate([SAMPLE,SAMPLE+' Another sentence changes the cadence.'],'x')
    assert p['name']=='x' and 'sentence_words_mean' in p['metrics']
