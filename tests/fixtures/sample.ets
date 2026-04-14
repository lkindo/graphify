// ArkTS (HarmonyOS) sample — covers V1 + V2 decorators, struct, and state.
import { TitleBar } from './TitleBar'
import { common } from '@kit.AbilityKit'

interface CheckRule {
  passMessage: string
  passValue: number
}

enum CheckState {
  NOT_START = 0,
  CHECKING = 1,
  DONE = 2,
}

@ObservedV2
class CheckBean {
  @Trace state: CheckState = CheckState.NOT_START
  iconID: Resource = $r("app.media.icon")
}

@Entry({
  routeName: "EnvCheckPage"
})
@ComponentV2
export struct EnvCheckPage {
  @Local checkState: CheckState = CheckState.NOT_START
  @Local model: TitleBar.Model = new TitleBar.Model()
  private storageId: number = -1
  @State oldFashionedState: string = "hello"

  aboutToAppear(): void {
    this.startCheck()
  }

  build() {
    Column() {
      Text("环境检测")
        .fontSize(16)
    }
  }

  private startCheck(): void {
    this.checkState = CheckState.CHECKING
  }
}

@Component
struct LegacyPage {
  @Prop title: string = ""
  @Link shared: number

  build() {
    Text(this.title)
  }
}
