import streamlit as st
import base64
import textwrap

def render_svg(svg):
    """Renders the given svg string as a base64-encoded image."""
    b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
    html = f'<img src="data:image/svg+xml;base64,{b64}"/>'
    st.write(html, unsafe_allow_html=True)

def show_track_analysis():
    st.title("SVG Display Test in Streamlit (base64 img workaround)")

    st.header("Simple SVG test:")
    simple_svg = """
    <svg width="100" height="100" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
      <circle cx="50" cy="50" r="40" stroke="red" stroke-width="4" fill="yellow" />
    </svg>
    """
    st.code(textwrap.dedent(simple_svg), language='svg')
    st.write("Rendered SVG:")
    render_svg(simple_svg)

    st.header("Your complex track SVG:")

    complex_svg = """
    <svg xmlns:xlink="http://www.w3.org/1999/xlink" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 383.390625 642" preserveAspectRatio="xMidYMid meet" stroke-linejoin="round" class="absolute inset-0" width="383.390625"  height="642" >
        <path stroke="#5757E7" stroke-width="14px" fill="#000000" fill-opacity="0" d="M142.03,130.896L136.743,121.622L130.284,110.204L125.782,101.657L118.165,88.42L110.532,75.176L105.769,67.021L99.656,56.808L95.285,49.305L91.696,43.237L90.326,40.106L90.457,38.148L91.305,37.104L92.414,36.322L93.849,36.061L95.089,36.256L97.633,36.843L102.266,38.67L116.162,45.129L127.58,51.001L138.209,56.695L142.645,59.631L147.473,62.958L156.176,69.742L164.658,76.462L168.768,80.311L172.748,84.225L176.07,88.157L181.028,93.899L184.943,98.726L191.745,107.257L194.876,111.041L199.77,116.391L206.203,124.081L211.748,130.344L216.315,135.694L220.295,140.326L223.818,144.632L226.297,147.438L227.863,149.003L230.49,150.593L233.295,152.42L237.079,154.834L240.863,157.248L244.386,159.531L246.8,161.489L249.091,164.036L250.918,166.58L252.68,169.451L253.984,172.257L255.094,175.062L256.072,177.802L256.92,180.999L257.507,183.817L257.899,187.079L258.486,191.19L258.878,194.256L259.204,196.67L259.921,199.541L260.965,202.477L262.14,204.891L264.097,208.414L271.982,221.763L276.484,228.94L284.501,241.43L286.785,245.018L289.525,249.846L293.048,255.28L295.593,259.195L297.876,262.718L300.16,266.828L302.313,270.547L304.342,274.69L306.3,279.257L307.996,283.824L309.497,288.457L311.65,295.246L313.607,301.771L315.564,308.034L317.195,314.036L318.565,318.929L320.066,324.148L320.979,328.454L322.545,334.065L324.437,340.067L325.612,344.112L328.963,355.666L331.964,365.061L333.986,371.911L337.836,384.779L339.989,392.738L342.076,400.176L345.469,411.907L347.818,419.736L350.362,428.155L351.667,431.939L353.951,438.986L355.321,444.037"/>
    </svg>
    """
    st.code(textwrap.dedent(complex_svg), language='svg')
    st.write("Rendered SVG:")
    render_svg(complex_svg)

if __name__ == "__main__":
    show_track_analysis()
